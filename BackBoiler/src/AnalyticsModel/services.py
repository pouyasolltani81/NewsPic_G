from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q, F, Min, Max
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
import json
from django.db import connection
from .models import APIRequest, APIEndpoint, UserSession, SystemMetrics

from django.views.decorators.clickjacking import xframe_options_exempt
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse , OpenApiExample

from .serializers import AnalyticsOverviewSerializer ,EndpointMetricsSerializer
from drf_spectacular.types import OpenApiTypes
from LogModel.log_handler import print_log



# Import config utilities
try:
    from app.config_utils import is_analytics_enabled, config_manager
except ImportError:
    # Fallback if config system not available
    is_analytics_enabled = lambda: True
    config_manager = None


User = get_user_model()

def is_staff(user):
    return user.is_staff

@login_required
@user_passes_test(is_staff)
@xframe_options_exempt  
def analytics_dashboard(request):
    # Check if analytics is enabled
    if not is_analytics_enabled():
        from django.http import HttpResponse
        return HttpResponse("Analytics is currently disabled.", status=503)
    
    return render(request, 'AnalyticsModel/dashboard.html')


class AnalyticsAPIView(APIView):
    @extend_schema(
        summary="Get analytics metrics",
        description="Retrieve analytics data for different metric types (overview, users, endpoints, realtime, errors, performance, geographic, devices).",
        parameters=[
            OpenApiParameter(
                name='metric_type',
                location=OpenApiParameter.PATH,
                required=True,
                description="The type of metric to retrieve",
                enum=['overview', 'users', 'endpoints', 'realtime', 'errors', 'performance', 'geographic', 'devices']
            ),
            OpenApiParameter(
                name='range',
                location=OpenApiParameter.QUERY,
                required=False,
                description="Time range for metrics",
                enum=['1h', '24h', '7d', '30d'],
                type=str
            ),
        ],
        responses={
            200: AnalyticsOverviewSerializer, 
            400: OpenApiResponse(description="Invalid metric type"),
            403: OpenApiResponse(description="Unauthorized"),
            503: OpenApiResponse(description="Feature disabled")
        }
    )
    def get(self, request, metric_type):
        if not request.user.is_staff:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if analytics is enabled
        if not is_analytics_enabled():
            return Response({'error': 'Analytics is currently disabled'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get time range from query params
        time_range = request.GET.get('range', '24h')
        end_time = timezone.now()
        
        if time_range == '1h':
            start_time = end_time - timedelta(hours=1)
        elif time_range == '24h':
            start_time = end_time - timedelta(days=1)
        elif time_range == '7d':
            start_time = end_time - timedelta(days=7)
        elif time_range == '30d':
            start_time = end_time - timedelta(days=30)
        else:
            start_time = end_time - timedelta(days=1)
        
        if metric_type == 'overview':
            return Response(self._get_overview_metrics(start_time, end_time))
        elif metric_type == 'endpoints':
            return Response(self._get_endpoint_metrics(start_time, end_time))
        elif metric_type == 'users':
            return Response(self._get_user_metrics(start_time, end_time))
        elif metric_type == 'realtime':
            return Response(self._get_realtime_metrics())
        elif metric_type == 'errors':
            # Check if error tracking is enabled
            if not self._is_error_tracking_enabled():
                return Response({'error': 'Error tracking is disabled'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response(self._get_error_metrics(start_time, end_time))
        elif metric_type == 'performance':
            return Response(self._get_performance_metrics(start_time, end_time))
        elif metric_type == 'geographic':
            # Check if GeoIP is enabled
            if not self._is_geoip_enabled():
                return Response({'error': 'Geographic tracking is disabled'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response(self._get_geographic_metrics(start_time, end_time))
        elif metric_type == 'devices':
            return Response(self._get_device_metrics(start_time, end_time))
        else:
            return Response({'error': 'Invalid metric type'}, status=status.HTTP_400_BAD_REQUEST)
    
    def _is_error_tracking_enabled(self):
        """Check if error tracking is enabled from config"""
        if config_manager:
            return config_manager.get('analytics.error_tracking', True)
        return True
    
    def _is_geoip_enabled(self):
        """Check if GeoIP is enabled from config"""
        if config_manager:
            return config_manager.get('analytics.geoip_enabled', True)
        return True
    
    def _get_overview_metrics(self, start_time, end_time):
        # Total requests
        total_requests = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).count()
        
        # Average response time
        avg_response_time = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).aggregate(avg=Avg('response_time'))['avg'] or 0
        
        # Error rate
        error_count = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time,
            status_code__gte=400
        ).count()
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        # Active users
        active_users = UserSession.objects.filter(
            last_activity__gte=start_time,
            last_activity__lte=end_time
        ).values('user').distinct().count()
        
        # Total users
        total_users = User.objects.count()
        
        # Online users (active in last 5 minutes)
        online_users = UserSession.objects.filter(
            last_activity__gte=timezone.now() - timedelta(minutes=5),
            is_active=True
        ).values('user').distinct().count()
        
        # Top endpoints
        top_endpoints = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values('endpoint__path', 'endpoint__method').annotate(
            count=Count('id'),
            avg_time=Avg('response_time')
        ).order_by('-count')[:5]
        
        # Request trend (hourly for last 24h, daily for longer periods)
        if (end_time - start_time).days <= 1:
            # Hourly trend
            trend_data = self._get_hourly_trend(start_time, end_time)
        else:
            # Daily trend
            trend_data = self._get_daily_trend(start_time, end_time)
        
        return {
            'total_requests': total_requests,
            'avg_response_time': round(avg_response_time, 2),
            'error_rate': round(error_rate, 2),
            'active_users': active_users,
            'total_users': total_users,
            'online_users': online_users,
            'top_endpoints': list(top_endpoints),
            'trend_data': trend_data
        }
    
    def _get_endpoint_metrics(self, start_time, end_time):
        endpoints = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values(
            'endpoint__path', 
            'endpoint__method',
            'endpoint__description'
        ).annotate(
            total_requests=Count('id'),
            avg_response_time=Avg('response_time'),
            min_response_time=Min('response_time'),
            max_response_time=Max('response_time'),
            error_count=Count('id', filter=Q(status_code__gte=400)),
            success_count=Count('id', filter=Q(status_code__lt=400)),
            unique_users=Count('user', distinct=True)
        ).order_by('-total_requests')
        
        # Status code distribution for each endpoint
        endpoint_status_codes = {}
        for endpoint in endpoints:
            key = f"{endpoint['endpoint__method']} {endpoint['endpoint__path']}"
            status_distribution = APIRequest.objects.filter(
                timestamp__gte=start_time,
                timestamp__lte=end_time,
                endpoint__path=endpoint['endpoint__path'],
                endpoint__method=endpoint['endpoint__method']
            ).values('status_code').annotate(
                count=Count('id')
            ).order_by('status_code')
            endpoint_status_codes[key] = list(status_distribution)
        
        return {
            'endpoints': list(endpoints),
            'status_codes': endpoint_status_codes
        }
    
    def _get_user_metrics(self, start_time, end_time):
        # Active users list with details
        active_users = UserSession.objects.filter(
            last_activity__gte=start_time,
            last_activity__lte=end_time
        ).select_related('user').values(
            'user__id',
            'user__username',
            'user__email',
            'user__first_name',
            'user__last_name'
        ).annotate(
            total_requests=Sum('api_calls'),
            avg_response_time=Avg(F('total_response_time') / F('api_calls')),
            session_count=Count('id'),
            last_seen=Max('last_activity')
        ).order_by('-total_requests')[:50]
        
        # User activity heatmap (by hour of day and day of week)
        heatmap_data = self._get_user_activity_heatmap(start_time, end_time)
        
        # New vs returning users
        new_users = User.objects.filter(
            date_joined__gte=start_time,
            date_joined__lte=end_time
        ).count()
        
        returning_users = UserSession.objects.filter(
            last_activity__gte=start_time,
            last_activity__lte=end_time,
            user__date_joined__lt=start_time
        ).values('user').distinct().count()
        
        # User retention (users who were active in previous period and current period)
        prev_end = start_time
        prev_start = start_time - (end_time - start_time)
        
        prev_active_users = set(UserSession.objects.filter(
            last_activity__gte=prev_start,
            last_activity__lte=prev_end
        ).values_list('user_id', flat=True))
        
        current_active_users = set(UserSession.objects.filter(
            last_activity__gte=start_time,
            last_activity__lte=end_time
        ).values_list('user_id', flat=True))
        
        retained_users = len(prev_active_users.intersection(current_active_users))
        retention_rate = (retained_users / len(prev_active_users) * 100) if prev_active_users else 0
        
        return {
            'active_users': list(active_users),
            'new_users': new_users,
            'returning_users': returning_users,
            'retention_rate': round(retention_rate, 2),
            'heatmap_data': heatmap_data
        }
    
    def _get_realtime_metrics(self):
        # Get cached real-time metrics
        metrics = cache.get('analytics:realtime:requests', {})
        
        # Get current online users
        online_users = UserSession.objects.filter(
            last_activity__gte=timezone.now() - timedelta(minutes=5),
            is_active=True
        ).select_related('user').values(
            'user__id',
            'user__username',
            'user__email',
            'ip_address',
            'user_agent'
        ).annotate(
            last_seen=Max('last_activity')
        )
        
        # Get active requests (last minute)
        current_minute = timezone.now().replace(second=0, microsecond=0)
        recent_requests = APIRequest.objects.filter(
            timestamp__gte=current_minute - timedelta(minutes=1)
        ).select_related('endpoint', 'user').values(
            'endpoint__path',
            'endpoint__method',
            'user__username',
            'status_code',
            'response_time',
            'timestamp'
        ).order_by('-timestamp')[:20]
        
        # Format metrics for frontend
        formatted_metrics = []
        for minute_str, data in sorted(metrics.items()):
            formatted_metrics.append({
                'timestamp': minute_str,
                'requests': data['count'],
                'avg_response_time': data['total_response_time'] / data['count'] if data['count'] > 0 else 0,
                'errors': data['errors'],
                'status_codes': data['status_codes']
            })
        
        return {
            'online_users': list(online_users),
            'recent_requests': list(recent_requests),
            'metrics_timeline': formatted_metrics[-60:]  # Last 60 minutes
        }
    
    def _get_error_metrics(self, start_time, end_time):
        
        
        
        # Most problematic endpoints
        problematic_endpoints = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time,
            status_code__gte=400
        ).values('endpoint__path', 'endpoint__method').annotate(
            error_count=Count('id')
        ).order_by('-error_count')[:10]
        
        return {
           
            'problematic_endpoints': list(problematic_endpoints)
        }
    
    def _get_performance_metrics(self, start_time, end_time):
        # Initialize percentiles with default values
        percentiles = {
            'p50': 0,
            'p75': 0,
            'p90': 0,
            'p95': 0,
            'p99': 0
        }
        
        # Response time percentiles
        response_times = list(APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values_list('response_time', flat=True).order_by('response_time'))
        
        total_count = len(response_times)
        if total_count > 0:
            percentiles = {
                'p50': response_times[int(total_count * 0.5)],
                'p75': response_times[int(total_count * 0.75)],
                'p90': response_times[int(total_count * 0.9)],
                'p95': response_times[int(total_count * 0.95)],
                'p99': response_times[min(int(total_count * 0.99), total_count - 1)]
            }
        
        # Slowest endpoints
        slow_endpoints = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values('endpoint__path', 'endpoint__method').annotate(
            avg_time=Avg('response_time'),
            max_time=Max('response_time'),
            request_count=Count('id')
        ).filter(request_count__gte=10).order_by('-avg_time')[:10]
        
        # Response time distribution
        time_buckets = [0, 100, 200, 500, 1000, 2000, 5000, 10000]  # milliseconds
        distribution = {}
        
        for i in range(len(time_buckets) - 1):
            bucket_name = f"{time_buckets[i]}-{time_buckets[i+1]}ms"
            count = APIRequest.objects.filter(
                timestamp__gte=start_time,
                timestamp__lte=end_time,
                response_time__gte=time_buckets[i],
                response_time__lt=time_buckets[i+1]
            ).count()
            distribution[bucket_name] = count
        
        # Add >10s bucket
        distribution['>10000ms'] = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time,
            response_time__gte=10000
        ).count()
        
        return {
            'percentiles': percentiles,
            'slow_endpoints': list(slow_endpoints),
            'response_time_distribution': distribution
        }
    
    def _get_geographic_metrics(self, start_time, end_time):
        # Check if GeoIP is enabled
        if not self._is_geoip_enabled():
            return {
                'countries': [],
                'cities': [],
                'message': 'Geographic tracking is disabled'
            }
        
        # Requests by country
        country_data = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).exclude(country__isnull=True).values('country').annotate(
            request_count=Count('id'),
            unique_users=Count('user', distinct=True),
            avg_response_time=Avg('response_time')
        ).order_by('-request_count')
        
        # Requests by city (top 20)
        city_data = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).exclude(city__isnull=True).values('city', 'country').annotate(
            request_count=Count('id'),
            unique_users=Count('user', distinct=True)
        ).order_by('-request_count')[:20]
        
        return {
            'countries': list(country_data),
            'cities': list(city_data)
        }
    
    def _get_device_metrics(self, start_time, end_time):
        # Device type distribution
        device_types = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values('device_type').annotate(
            count=Count('id'),
            unique_users=Count('user', distinct=True)
        ).order_by('-count')
        
        # Browser distribution
        browsers = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values('browser').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # OS distribution
        operating_systems = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values('os').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'device_types': list(device_types),
            'browsers': list(browsers),
            'operating_systems': list(operating_systems)
        }
    
    def _get_hourly_trend(self, start_time, end_time):
        # SQLite-compatible hourly trend
        trend = []
        current = start_time.replace(minute=0, second=0, microsecond=0)
        
        while current < end_time:
            next_hour = current + timedelta(hours=1)
            
            requests = APIRequest.objects.filter(
                timestamp__gte=current,
                timestamp__lt=next_hour
            )
            
            trend.append({
                'hour': current.isoformat(),
                'requests': requests.count(),
                'errors': requests.filter(status_code__gte=400).count(),
                'avg_response_time': requests.aggregate(avg=Avg('response_time'))['avg'] or 0
            })
            
            current = next_hour
        
        return trend
    
    def _get_daily_trend(self, start_time, end_time):
        # SQLite-compatible daily trend
        trend = []
        current = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current < end_time:
            next_day = current + timedelta(days=1)
            
            requests = APIRequest.objects.filter(
                timestamp__gte=current,
                timestamp__lt=next_day
            )
            
            trend.append({
                'day': current.isoformat(),
                'requests': requests.count(),
                'errors': requests.filter(status_code__gte=400).count(),
                'avg_response_time': requests.aggregate(avg=Avg('response_time'))['avg'] or 0,
                'unique_users': requests.values('user').distinct().count()
            })
            
            current = next_day
        
        return trend
    
    def _get_user_activity_heatmap(self, start_time, end_time):
        # Create a heatmap of user activity by hour of day and day of week
        # SQLite-compatible version
        heatmap = {}
        
        # Initialize heatmap
        for dow in range(7):
            for hour in range(24):
                key = f"{dow}_{hour}"
                heatmap[key] = 0
        
        # Get all requests in the time range
        requests = APIRequest.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        ).values_list('timestamp', flat=True)
        
        # Count requests by hour and day of week
        for timestamp in requests:
            dow = timestamp.weekday()  # 0 = Monday, 6 = Sunday
            # Convert to 0 = Sunday, 6 = Saturday for consistency
            dow = (dow + 1) % 7
            hour = timestamp.hour
            key = f"{dow}_{hour}"
            heatmap[key] += 1
        
        return heatmap
    
    
    
    
###############################################################################################################################################################
# System Metric Functions 
def collect_system_metrics():
    import psutil
    from django.db import connection
    from django.core.cache import cache
    
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    total_memory_gb = memory.total / (1024 ** 3)  
    
    # GPU metrics (if available)
    gpu_memory_percent = None
    gpu_total_memory_gb = None
    gpu_name = None
    gpu_temperature = None
    
    try:
        # Try to get GPU metrics using nvidia-ml-py
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        
        if device_count > 0:
            # Get first GPU's info
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            # Memory info
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_total_memory_gb = mem_info.total / (1024 ** 3)
            gpu_memory_percent = (mem_info.used / mem_info.total) * 100
            
            # GPU name
            gpu_name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
            
            # Temperature
            try:
                gpu_temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                pass
            
        pynvml.nvmlShutdown()
    except Exception:
        # No NVIDIA GPU or pynvml not installed
        # Try GPUtil as a fallback
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Get first GPU
                gpu_memory_percent = gpu.memoryUtil * 100
                gpu_total_memory_gb = gpu.memoryTotal / 1024  # MB to GB
                gpu_name = gpu.name
                gpu_temperature = gpu.temperature
        except Exception:
            pass
    
    # Disk usage
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    
    # Active connections (approximate)
    active_connections = len(psutil.net_connections())
    
    # Database connections
    with connection.cursor() as cursor:
        if connection.vendor == 'sqlite':
            db_connections = 1
        else:
            cursor.execute("SELECT count(*) FROM pg_stat_activity;")
            db_connections = cursor.fetchone()[0]
    
    # Cache hit rate for Django default cache
    cache_hit_rate = None
    try:
        if hasattr(cache, "_cache"):
            stats = getattr(cache._cache, "get_stats", lambda: [])()
            if stats and isinstance(stats, list) and len(stats) > 0:
                stat = stats[0][1]
                hits = stat.get("get_hits", 0)
                misses = stat.get("get_misses", 0)
                total = hits + misses
                cache_hit_rate = (hits / total) * 100 if total > 0 else None
    except Exception:
        cache_hit_rate = None
    
    # Save metrics
    SystemMetrics.objects.create(
        cpu_usage=cpu_percent,
        memory_usage=memory_percent,
        total_memory_gb=total_memory_gb,
        gpu_memory_usage=gpu_memory_percent,
        gpu_total_memory_gb=gpu_total_memory_gb,
        gpu_name=gpu_name,
        gpu_temperature=gpu_temperature,
        disk_usage=disk_percent,
        active_connections=active_connections,
        database_connections=db_connections,
        cache_hit_rate=cache_hit_rate
    )




class SystemCheckAPIView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='min_memory',
                description='Minimum memory required (e.g., "4.0" for 4 GB or "30%" for 30% free)',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='min_gpu_memory',
                description='Minimum GPU memory required (e.g., "2.0" for 2 GB or "30%" for 30% free)',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='max_cpu',
                description='Maximum CPU usage allowed (e.g., "80" for 80%)',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        tags=['System'],
        description="Returns comprehensive system metrics and optionally checks resource availability.",
        examples=[
            OpenApiExample(
                'Get all metrics',
                value={},
                request_only=True,
            ),
            OpenApiExample(
                'Check system memory',
                value={'min_memory': '4.0'},
                request_only=True,
            ),
            OpenApiExample(
                'Check GPU memory',
                value={'min_gpu_memory': '30%'},
                request_only=True,
            ),
            OpenApiExample(
                'Check multiple resources',
                value={'min_memory': '8.0', 'min_gpu_memory': '2.0', 'max_cpu': '80'},
                request_only=True,
            ),
        ]
    )
    def get(self, request):
        # Get query parameters
        min_memory = request.query_params.get("min_memory")
        min_gpu_memory = request.query_params.get("min_gpu_memory")
        max_cpu = request.query_params.get("max_cpu")
        
        try:
            # Collect fresh metrics
            try:
                collect_system_metrics()
            except Exception as e:
                print_log(
                    user=request.user if request.user.is_authenticated else None,
                    level='warning',
                    message=f"Could not collect fresh metrics: {e}",
                    exception_type='MetricsCollectionWarning',
                    file_path=__file__,
                    view_name='SystemCheckAPIView.get'
                )
            
            # Get latest metrics
            latest = SystemMetrics.objects.order_by('-timestamp').first()
            if not latest:
                return Response(
                    {"error": "No system metrics available"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Build comprehensive response
            response_data = {
                "timestamp": latest.timestamp.isoformat(),
                "system": {
                    "cpu": {
                        "usage_percent": round(latest.cpu_usage, 2),
                        "available_percent": round(100 - latest.cpu_usage, 2)
                    },
                    "memory": {
                        "total_gb": round(latest.total_memory_gb, 2),
                        "used_percent": round(latest.memory_usage, 2),
                        "free_percent": round(100 - latest.memory_usage, 2),
                        "free_gb": round(latest.total_memory_gb * (1 - latest.memory_usage / 100), 2),
                        "used_gb": round(latest.total_memory_gb * (latest.memory_usage / 100), 2)
                    },
                    "disk": {
                        "usage_percent": round(latest.disk_usage, 2),
                        "free_percent": round(100 - latest.disk_usage, 2)
                    },
                    "connections": {
                        "active": latest.active_connections,
                        "database": latest.database_connections
                    },
                    "cache": {
                        "hit_rate": round(latest.cache_hit_rate, 2) if latest.cache_hit_rate else None
                    },
                    "queue": {
                        "size": latest.queue_size
                    }
                }
            }
            
            # Add GPU info if available
            if latest.gpu_total_memory_gb is not None and latest.gpu_memory_usage is not None:
                response_data["gpu"] = {
                    "name": latest.gpu_name,
                    "memory": {
                        "total_gb": round(latest.gpu_total_memory_gb, 2),
                        "used_percent": round(latest.gpu_memory_usage, 2),
                        "free_percent": round(100 - latest.gpu_memory_usage, 2),
                        "free_gb": round(latest.gpu_total_memory_gb * (1 - latest.gpu_memory_usage / 100), 2),
                        "used_gb": round(latest.gpu_total_memory_gb * (latest.gpu_memory_usage / 100), 2)
                    },
                    "temperature": round(latest.gpu_temperature, 1) if latest.gpu_temperature else None
                }
            else:
                response_data["gpu"] = None
            
            # Perform checks if requested
            checks = {}
            
            # Check system memory
            if min_memory:
                try:
                    memory_ok = self._check_memory(latest, min_memory, is_gpu=False)
                    checks["memory_ok"] = memory_ok
                except ValueError as ve:
                    return Response(
                        {"error": f"Invalid min_memory parameter: {ve}"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check GPU memory
            if min_gpu_memory:
                if response_data["gpu"] is None:
                    checks["gpu_memory_ok"] = False
                    checks["gpu_memory_error"] = "No GPU detected"
                else:
                    try:
                        gpu_ok = self._check_memory(latest, min_gpu_memory, is_gpu=True)
                        checks["gpu_memory_ok"] = gpu_ok
                    except ValueError as ve:
                        return Response(
                            {"error": f"Invalid min_gpu_memory parameter: {ve}"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            # Check CPU usage
            if max_cpu:
                try:
                    max_cpu_float = float(max_cpu)
                    if max_cpu_float < 0 or max_cpu_float > 100:
                        raise ValueError("CPU percentage must be between 0 and 100")
                    checks["cpu_ok"] = latest.cpu_usage <= max_cpu_float
                except ValueError as ve:
                    return Response(
                        {"error": f"Invalid max_cpu parameter: {ve}"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Add checks to response if any were performed
            if checks:
                response_data["checks"] = checks
                # Add overall status
                response_data["all_checks_passed"] = all(
                    v for k, v in checks.items() 
                    if k.endswith('_ok')
                )
            
            return Response(response_data)
            
        except Exception as e:
            print_log(
                user=request.user if request.user.is_authenticated else None,
                level='error',
                message=f"Unexpected error in system check: {e}",
                exception_type='UnexpectedError',
                file_path=__file__,
                view_name='SystemCheckAPIView.get'
            )
            return Response(
                {"error": "An unexpected error occurred while checking system metrics."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _check_memory(self, metrics, requirement, is_gpu=False):
        """Helper method to check memory requirements"""
        if is_gpu:
            total_gb = metrics.gpu_total_memory_gb
            used_percent = metrics.gpu_memory_usage
        else:
            total_gb = metrics.total_memory_gb
            used_percent = metrics.memory_usage
        
        free_gb = total_gb * (1 - used_percent / 100)
        free_percent = 100 - used_percent
        
        requirement_str = str(requirement).strip()
        
        if requirement_str.endswith('%'):
            required_percent = float(requirement_str.rstrip('%'))
            if required_percent < 0 or required_percent > 100:
                raise ValueError(f"Percentage must be between 0 and 100, got {required_percent}")
            
            is_ok = free_percent >= required_percent
            
            if not is_ok:
                resource_type = "GPU" if is_gpu else "System"
                print_log(
                    user=None,
                    level='info',
                    message=f"Not enough {resource_type} memory: required {required_percent}%, available {free_percent:.2f}%",
                    exception_type='InsufficientMemory',
                    file_path=__file__,
                    view_name='SystemCheckAPIView._check_memory'
                )
            
            return is_ok
        else:
            required_gb = float(requirement_str)
            if required_gb < 0:
                raise ValueError(f"Memory requirement cannot be negative: {required_gb}")
            
            is_ok = free_gb >= required_gb
            
            if not is_ok:
                resource_type = "GPU" if is_gpu else "System"
                print_log(
                    user=None,
                    level='info',
                    message=f"Not enough {resource_type} memory: required {required_gb}GB, available {free_gb:.2f}GB",
                    exception_type='InsufficientMemory',
                    file_path=__file__,
                    view_name='SystemCheckAPIView._check_memory'
                )
            
            return is_ok