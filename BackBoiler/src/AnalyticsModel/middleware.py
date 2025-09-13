import time
import json
import traceback
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from user_agents import parse
# import geoip2.database
from django.conf import settings
from .models import APIEndpoint, APIRequest, UserSession
from django.db import transaction, IntegrityError
import logging

logger = logging.getLogger(__name__)

class AnalyticsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.geoip_reader = None
        
        # # Only initialize GeoIP if enabled in config
        # if self._is_geoip_enabled():
        #     self._initialize_geoip()
    
    # def _initialize_geoip(self):
    #     """Initialize GeoIP reader if enabled and database exists"""
    #     try:
    #         from django.conf import settings
    #         geoip_path = getattr(settings, 'GEOIP_PATH', None)
    #         if geoip_path:
    #             import geoip2.database
    #             self.geoip_reader = geoip2.database.Reader(
    #                 geoip_path + '/GeoLite2-City.mmdb'
    #             )
    #             logger.info("GeoIP reader initialized successfully")
    #         else:
    #             logger.warning("GEOIP_PATH not configured in settings")
    #     except Exception as e:
    #         self.geoip_reader = None
    #         logger.warning(f"Failed to initialize GeoIP reader: {e}")
    
    def _is_analytics_enabled(self):
        """Check if analytics is enabled from config"""
        try:
            from app.config_utils import is_analytics_enabled
            return is_analytics_enabled()
        except ImportError:
            # Fallback if config system not available
            return True
    
    def _should_sample_request(self):
        """Check if this request should be sampled based on sample_rate"""
        try:
            from app.config_utils import get_analytics_sample_rate
            import random
            sample_rate = get_analytics_sample_rate()
            return random.random() < sample_rate
        except ImportError:
            # Fallback if config system not available
            return True
    
    def _is_geoip_enabled(self):
        """Check if GeoIP is enabled from config"""
        try:
            from app.config_utils import config_manager
            return config_manager.get('analytics.geoip_enabled', True)
        except ImportError:
            # Fallback if config system not available
            return True
    
    def _should_track_session(self):
        """Check if session tracking is enabled"""
        try:
            from app.config_utils import config_manager
            return config_manager.get('analytics.session_tracking', True)
        except ImportError:
            # Fallback if config system not available
            return True
    
    def _should_track_errors(self):
        """Check if error tracking is enabled"""
        try:
            from app.config_utils import config_manager
            return config_manager.get('analytics.error_tracking', True)
        except ImportError:
            # Fallback if config system not available
            return True

    def __call__(self, request):
        # Check if analytics is enabled globally
        if not self._is_analytics_enabled():
            return self.get_response(request)
        
        # Check if this request should be sampled
        if not self._should_sample_request():
            return self.get_response(request)
        
        # Skip analytics for static files, admin, and internal Django paths
        if self._should_skip_request(request):
            return self.get_response(request)

        start_time = time.time()
        
        # Pre-request processing
        request_body_size = len(request.body) if request.body else 0
        
        # Get or create session (only if session tracking is enabled)
        session = None
        if self._should_track_session():
            session = self._get_or_create_session(request)
        
        # Process request
        response = None
        error_data = None
        
        try:
            response = self.get_response(request)
        except Exception as e:
            # Only track errors if error tracking is enabled
            if self._should_track_errors():
                error_data = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc()
                }
            # Re-raise the exception
            raise
        finally:
            # Calculate response time
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Log the request asynchronously
            try:
                self._log_request_async(
                    request, 
                    response, 
                    response_time, 
                    request_body_size,
                    session,
                    error_data
                )
            except Exception as e:
                logger.error(f"Failed to log analytics: {str(e)}")
            
            # Update session activity (only if session tracking is enabled)
            if session and self._should_track_session():
                try:
                    self._update_session_activity(session, response_time)
                except Exception as e:
                    logger.error(f"Failed to update session activity: {str(e)}")
        
        return response

    def _should_skip_request(self, request):
        skip_paths = [
            '/static/', 
            '/media/', 
            '/admin/jsi18n/', 
            '/__debug__/',
            '/__reload__/',  # Django auto-reload
            '/favicon.ico',
            '/.well-known/',
            '/robots.txt',
            '/analytics/api/',
            '/Dashoboard/',
        ]
        return any(request.path.startswith(path) for path in skip_paths)

    def _get_or_create_session(self, request):
        if isinstance(request.user, AnonymousUser):
            return None
            
        session_key = request.session.session_key
        if not session_key:
            return None
            
        try:
            # Try to get existing active session
            session = UserSession.objects.get(
                session_key=session_key,
                is_active=True
            )
            return session
        except UserSession.DoesNotExist:
            # Create new session, handling potential race conditions
            try:
                return UserSession.objects.create(
                    user=request.user,
                    session_key=session_key,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except IntegrityError:
                # Session was created by another request in the meantime
                try:
                    return UserSession.objects.get(
                        session_key=session_key,
                        is_active=True
                    )
                except UserSession.DoesNotExist:
                    # Session exists but is inactive, update it
                    UserSession.objects.filter(
                        session_key=session_key
                    ).update(
                        is_active=True,
                        user=request.user,
                        last_activity=timezone.now()
                    )
                    return UserSession.objects.get(session_key=session_key)
        except Exception as e:
            logger.error(f"Error in session handling: {str(e)}")
            return None

    def _log_request_async(self, request, response, response_time, request_body_size, session, error_data):
        # In production, you'd want to use Celery for this
        # For now, we'll do it synchronously with transaction
        try:
            with transaction.atomic():
                # Get or create endpoint
                endpoint = self._get_or_create_endpoint(request)
                if not endpoint:
                    return
                
                # Parse user agent
                user_agent_string = request.META.get('HTTP_USER_AGENT', '')
                user_agent = parse(user_agent_string)
                
                # Get geographic info
                ip_address = self._get_client_ip(request)
                geo_info = self._get_geo_info(ip_address)
                
                # Create API request log
                api_request = APIRequest.objects.create(
                    endpoint=endpoint,
                    user=request.user if not isinstance(request.user, AnonymousUser) else None,
                    response_time=response_time,
                    status_code=response.status_code if response else 500,
                    ip_address=ip_address,
                    user_agent=user_agent_string,
                    request_body_size=request_body_size,
                    response_body_size=len(response.content) if response and hasattr(response, 'content') else 0,
                    device_type=self._get_device_type(user_agent),
                    browser=f"{user_agent.browser.family} {user_agent.browser.version_string}" if user_agent.browser.family else "Unknown",
                    os=f"{user_agent.os.family} {user_agent.os.version_string}" if user_agent.os.family else "Unknown",
                    country=geo_info.get('country'),
                    city=geo_info.get('city'),
                    query_params=dict(request.GET),
                    headers=self._get_safe_headers(request),
                    error_message=error_data.get('error_message') if error_data else None,
                    traceback=error_data.get('traceback') if error_data else None
                )
                
                
                # Update cache for real-time metrics
                self._update_realtime_metrics(request, response, response_time)
                
        except Exception as e:
            logger.error(f"Failed to log analytics: {str(e)}")

    def _get_or_create_endpoint(self, request):
        path = request.path
        method = request.method
        
        try:
            endpoint, created = APIEndpoint.objects.get_or_create(
                path=path,
                method=method,
                defaults={
                    'view_name': request.resolver_match.view_name if request.resolver_match else None,
                    'description': self._get_endpoint_description(request)
                }
            )
            return endpoint
        except Exception as e:
            logger.error(f"Failed to get/create endpoint: {str(e)}")
            return None

    def _get_endpoint_description(self, request):
        # Try to get description from view docstring
        if request.resolver_match and request.resolver_match.func:
            return request.resolver_match.func.__doc__ or ''
        return ''
        
    def _get_client_ip(self,request):
        """Get client IP address from various headers"""
        # Check headers in order of preference
        headers = [
            'HTTP_CF_CONNECTING_IP',  # Cloudflare
            'HTTP_X_REAL_IP',         # Nginx
            'HTTP_X_FORWARDED_FOR',   # Standard proxy header
            'HTTP_X_FORWARDED',       # Less common
            'HTTP_X_CLUSTER_CLIENT_IP',
            'HTTP_FORWARDED_FOR',
            'HTTP_FORWARDED',
            'REMOTE_ADDR'             # Direct connection
        ]
        
        for header in headers:
            ip = request.META.get(header)
            if ip:
                # Handle comma-separated IPs (proxy chains)
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                # Remove port if present
                if ':' in ip and not ip.count(':') > 1:  # Not IPv6
                    ip = ip.split(':')[0]
                # Skip localhost/private IPs if we have better options
                if ip and not ip.startswith(('127.', '10.', '192.168.', '172.')):
                    return ip
                elif ip and header == 'REMOTE_ADDR':  # Use as fallback
                    return ip
        
        return request.META.get('REMOTE_ADDR', '127.0.0.1')

    
    def _get_geo_info(self, ip_address):
        # Check if GeoIP is enabled
        if not self._is_geoip_enabled():
            return {'country': None, 'city': None}
        
        if ip_address.startswith(('192.168.', '10.', '172.')) or ip_address == '127.0.0.1':
            logger.info(f"Skipping private IP: {ip_address}")
            return {'country': None, 'city': None}
        
        try:
            import requests
            response = requests.get(f'https://ipapi.co/{ip_address}/json/', timeout=2)
            if response.status_code == 200:
                data = response.json()
                result = {
                    'country': data.get('country_name'),
                    'city': data.get('city')
                }
                logger.info(f"GeoIP lookup for {ip_address}: {result}")
                return result
            else:
                logger.warning(f"GeoIP API returned status {response.status_code} for IP {ip_address}")
        except Exception as e:
            logger.error(f"GeoIP lookup failed for {ip_address}: {str(e)}")
        
        return {'country': None, 'city': None}
    # Replace the _get_geo_info method:
    # def _get_geo_info(self, ip_address):
    #     if ip_address.startswith('192.168.') or ip_address.startswith('10.') or ip_address == '127.0.0.1':
    #         return {'country': None, 'city': None}
        
    #     try:
    #         # Using ip-api.com (free, no API key needed, 45 requests per minute)
    #         import requests
    #         response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=1)
    
    #         if response.status_code == 200:
    #             data = response.json()
    #             if data['status'] == 'success':
    #                 return {
    #                     'country': data.get('country'),
    #                     'city': data.get('city')
    #                 }
    #     except:
    #         pass
        
    #     return {'country': None, 'city': None}

    # def _get_geo_info(self, ip_address):
    #     if not self.geoip_reader or ip_address.startswith('192.168.') or ip_address == '127.0.0.1':
    #         return {'country': None, 'city': None}
            
    #     try:
    #         response = self.geoip_reader.city(ip_address)
    #         return {
    #             'country': response.country.name,
    #             'city': response.city.name
    #         }
    #     except:
    #         return {'country': None, 'city': None}

    def _get_device_type(self, user_agent):
        if user_agent.is_mobile:
            return 'mobile'
        elif user_agent.is_tablet:
            return 'tablet'
        elif user_agent.is_pc:
            return 'desktop'
        else:
            return 'unknown'

    def _get_safe_headers(self, request):
        # Only include safe headers
        safe_headers = [
            'HTTP_ACCEPT', 'HTTP_ACCEPT_LANGUAGE', 'HTTP_ACCEPT_ENCODING',
            'HTTP_HOST', 'HTTP_REFERER', 'HTTP_USER_AGENT', 'CONTENT_TYPE'
        ]
        return {
            key: request.META.get(key, '')
            for key in safe_headers
            if key in request.META
        }

    def _update_session_activity(self, session, response_time):
        if not session:
            return
            
        try:
            session.last_activity = timezone.now()
            session.api_calls += 1
            session.total_response_time += response_time
            session.save(update_fields=['last_activity', 'api_calls', 'total_response_time'])
        except Exception as e:
            logger.error(f"Failed to update session: {str(e)}")

    def _update_realtime_metrics(self, request, response, response_time):
        try:
            # Update real-time metrics in cache
            cache_key = 'analytics:realtime:requests'
            current_minute = timezone.now().replace(second=0, microsecond=0)
            
            # Get or create metrics for current minute
            metrics = cache.get(cache_key, {})
            minute_key = current_minute.isoformat()
            
            if minute_key not in metrics:
                metrics[minute_key] = {
                    'count': 0,
                    'total_response_time': 0,
                    'errors': 0,
                    'status_codes': {}
                }
            
            metrics[minute_key]['count'] += 1
            metrics[minute_key]['total_response_time'] += response_time
            
            if response:
                status_code = str(response.status_code)
                metrics[minute_key]['status_codes'][status_code] = \
                    metrics[minute_key]['status_codes'].get(status_code, 0) + 1
                
                if response.status_code >= 400:
                    metrics[minute_key]['errors'] += 1
            
            # Keep only last 60 minutes
            cutoff_time = current_minute - timezone.timedelta(minutes=60)
            metrics = {
                k: v for k, v in metrics.items()
                if timezone.datetime.fromisoformat(k) > cutoff_time
            }
            
            cache.set(cache_key, metrics, 3600)  # Cache for 1 hour
        except Exception as e:
            logger.error(f"Failed to update realtime metrics: {str(e)}")