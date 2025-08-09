from django.db import models
from django.utils import timezone
from datetime import timedelta
from UserModel.models import User
from django.http import JsonResponse
from functools import wraps
from app.app_lib import get_client_ip
from LogModel.log_handler import print_log

RATE_LIMIT_ENDPOINTS = {
    'api_general': {'limit': 10, 'window_minutes': 2},
    'login_rate': {'limit': 5, 'window_minutes': 5},
    'register_rate': {'limit': 5, 'window_minutes': 10},
    'password_reset_rate': {'limit': 5, 'window_minutes': 10},
    'profile_update_rate': {'limit': 20, 'window_minutes': 60},
    'user_uuid_rate': {'limit': 5, 'window_minutes': 1},
    'data_fetch_rate': {'limit': 50, 'window_minutes': 60},
    'data_upload_rate': {'limit': 30, 'window_minutes': 60},
    'api_search_rate': {'limit': 20, 'window_minutes': 10},
    'api_user_auth_rate': {'limit': 10, 'window_minutes': 5},
}

class RateLimit(models.Model):
    ip_address = models.GenericIPAddressField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    endpoint = models.CharField(max_length=50, default='api_general')
    request_count = models.IntegerField(default=1)
    window_start = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['ip_address', 'user', 'endpoint', 'window_start']
        indexes = [
            models.Index(fields=['ip_address', 'endpoint', 'window_start']),
            models.Index(fields=['user', 'endpoint', 'window_start']),
        ]
    
    @classmethod
    def check_rate_limit(cls, ip_address, endpoint, limit, window_minutes, user=None):
        """Check if rate limit is exceeded"""
        window_start = timezone.now() - timedelta(minutes=window_minutes)
        
        # Clean old records
        cls.objects.filter(ip_address=ip_address, user=user, endpoint=endpoint, window_start__lt=window_start).delete()

        try:
            record, created = cls.objects.get_or_create(ip_address=ip_address, user=user, endpoint=endpoint)
            
            if not created:
                record.request_count += 1
                record.save()
            
            # Check if limit exceeded
            total_requests = cls.objects.filter(
                ip_address=ip_address,
                user=user,
                endpoint=endpoint
            ).aggregate(total=models.Sum('request_count'))['total'] or 0
            
            return total_requests > limit
            
        except Exception:
            return False
#############################################################################################
class BlackList(models.Model):
    BLACKLIST_TYPES = [
        ('ip', 'IP Address'),
        ('user', 'User Account'),
        ('both', 'IP and User'),
    ]
    
    REASON_CHOICES = [
        ('rate_limit_abuse', 'Rate Limit Abuse'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('security_violation', 'Security Violation'),
        ('spam', 'Spam/Bot Activity'),
        ('manual', 'Manual Block'),
        ('automated', 'Automated Detection'),
    ]
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    blacklist_type = models.CharField(max_length=10, choices=BLACKLIST_TYPES, default='ip')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES, default='rate_limit_abuse')
    description = models.TextField(blank=True, null=True)
    
    # Blacklist duration settings
    is_permanent = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking fields
    violation_count = models.IntegerField(default=1)
    last_violation = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Admin fields
    created_by = models.CharField(max_length=50, default='system')  # 'system' or admin username
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at', 'is_active']),
        ]
        unique_together = ['ip_address', 'user', 'blacklist_type']
    
    def __str__(self):
        if self.blacklist_type == 'ip':
            return f"IP Blacklist: {self.ip_address}"
        elif self.blacklist_type == 'user':
            return f"User Blacklist: {self.user}"
        else:
            return f"Combined Blacklist: {self.ip_address} - {self.user}"
    
    @property
    def is_expired(self):
        """Check if blacklist entry has expired"""
        if self.is_permanent:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False
    
    @classmethod
    def is_blacklisted(cls, ip_address, user=None):
        """Check if IP or user is blacklisted"""
        now = timezone.now()
        
        # Clean expired entries
        cls.objects.filter(
            expires_at__lt=now,
            is_permanent=False,
            is_active=True
        ).update(is_active=False)
        
        # Check IP blacklist
        ip_blacklisted = cls.objects.filter( ip_address=ip_address, blacklist_type__in=['ip', 'both'], is_active=True).filter(
            models.Q(is_permanent=True) | models.Q(expires_at__gt=now)).exists()
        
        if ip_blacklisted:
            return True, 'ip'
        
        # Check user blacklist if user is provided
        if user and user.is_authenticated:
            user_blacklisted = cls.objects.filter(
                user=user,
                blacklist_type__in=['user', 'both'],
                is_active=True
            ).filter(
                models.Q(is_permanent=True) | models.Q(expires_at__gt=now)
            ).exists()
            
            if user_blacklisted:
                return True, 'user'
        
        return False, None
    
    @classmethod
    def add_to_blacklist(cls, ip_address=None, user=None, reason='rate_limit_abuse', 
                        duration_hours=24, description=None, created_by='system'):
        """Add IP/User to blacklist"""
        if not ip_address and not user:
            return None
        
        blacklist_type = 'both' if ip_address and user else ('ip' if ip_address else 'user')
        expires_at = timezone.now() + timedelta(hours=duration_hours) if duration_hours else None
        
        try:
            blacklist_entry, created = cls.objects.get_or_create(
                ip_address=ip_address,
                user=user,
                blacklist_type=blacklist_type,
                defaults={
                    'reason': reason,
                    'description': description,
                    'expires_at': expires_at,
                    'created_by': created_by,
                    'is_permanent': duration_hours is None,
                }
            )
            
            if not created:
                # Update existing entry
                blacklist_entry.violation_count += 1
                blacklist_entry.last_violation = timezone.now()
                blacklist_entry.is_active = True
                if duration_hours:
                    blacklist_entry.expires_at = timezone.now() + timedelta(hours=duration_hours)
                blacklist_entry.save()
            
            return blacklist_entry
            
        except Exception as e:
            print_log(level='error', message=f"Failed to add blacklist entry: {str(e)}", exception_type='BlacklistError', file_path=__file__, line_number=cls.add_to_blacklist.__code__.co_firstlineno, view_name='RateLimit.add_to_blacklist')
            return None
    
    @classmethod
    def remove_from_blacklist(cls, ip_address=None, user=None):
        """Remove IP/User from blacklist"""
        filters = {}
        if ip_address:
            filters['ip_address'] = ip_address
        if user:
            filters['user'] = user
        
        if filters:
            cls.objects.filter(**filters).update(is_active=False)
            return True
        return False

#############################################################################################
class WhiteList(models.Model):
    WHITELIST_TYPES = [
        ('ip', 'IP Address'),
        ('user', 'User Account'),
        ('both', 'IP and User'),
    ]
    
    REASON_CHOICES = [
        ('trusted_user', 'Trusted User'),
        ('admin_user', 'Administrator'),
        ('api_service', 'API Service'),
        ('internal_system', 'Internal System'),
        ('vip_user', 'VIP User'),
        ('testing', 'Testing Purpose'),
        ('manual', 'Manual Whitelist'),
        ('automated', 'Automated Whitelist'),
    ]
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    whitelist_type = models.CharField(max_length=10, choices=WHITELIST_TYPES, default='ip')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES, default='trusted_user')
    description = models.TextField(blank=True, null=True)
    
    # Whitelist duration settings
    is_permanent = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking fields
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Admin fields
    created_by = models.CharField(max_length=50, default='system')  # 'system' or admin username
    is_active = models.BooleanField(default=True)
    
    # Rate limit bypass settings
    bypass_rate_limits = models.BooleanField(default=True, help_text="Bypass all rate limiting")
    custom_rate_multiplier = models.FloatField(default=1.0, help_text="Rate limit multiplier (e.g., 2.0 = double the limits)")
    
    class Meta:
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at', 'is_active']),
        ]
        unique_together = ['ip_address', 'user', 'whitelist_type']
        verbose_name = 'White List'
        verbose_name_plural = 'White Lists'
    
    def __str__(self):
        if self.whitelist_type == 'ip':
            return f"IP Whitelist: {self.ip_address}"
        elif self.whitelist_type == 'user':
            return f"User Whitelist: {self.user}"
        else:
            return f"Combined Whitelist: {self.ip_address} - {self.user}"
    
    @property
    def is_expired(self):
        """Check if whitelist entry has expired"""
        if self.is_permanent:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False
    
    @classmethod
    def is_whitelisted(cls, ip_address, user=None):
        """Check if IP or user is whitelisted"""
        now = timezone.now()
        
        # Clean expired entries
        cls.objects.filter(expires_at__lt=now, is_permanent=False, is_active=True).update(is_active=False)
        
        # Check IP whitelist
        ip_whitelisted = cls.objects.filter(ip_address=ip_address, whitelist_type__in=['ip', 'both'], is_active=True).filter(
            models.Q(is_permanent=True) | models.Q(expires_at__gt=now)
        ).first()
        
        if ip_whitelisted:
            # Update usage tracking
            ip_whitelisted.usage_count += 1
            ip_whitelisted.last_used = now
            ip_whitelisted.save(update_fields=['usage_count', 'last_used'])
            return True, 'ip', ip_whitelisted
        
        # Check user whitelist if user is provided
        if user and user.is_authenticated:
            user_whitelisted = cls.objects.filter(user=user, whitelist_type__in=['user', 'both'], is_active=True).filter(
                models.Q(is_permanent=True) | models.Q(expires_at__gt=now)
            ).first()
            
            if user_whitelisted:
                # Update usage tracking
                user_whitelisted.usage_count += 1
                user_whitelisted.last_used = now
                user_whitelisted.save(update_fields=['usage_count', 'last_used'])
                return True, 'user', user_whitelisted
        
        return False, None, None
    
    @classmethod
    def add_to_whitelist(cls, ip_address=None, user=None, reason='trusted_user', 
                        duration_hours=None, description=None, created_by='system',
                        bypass_rate_limits=True, custom_rate_multiplier=1.0):
        """Add IP/User to whitelist"""
        if not ip_address and not user:
            return None
        
        whitelist_type = 'both' if ip_address and user else ('ip' if ip_address else 'user')
        expires_at = timezone.now() + timedelta(hours=duration_hours) if duration_hours else None
        
        try:
            whitelist_entry, created = cls.objects.get_or_create(
                ip_address=ip_address,
                user=user,
                whitelist_type=whitelist_type,
                defaults={
                    'reason': reason,
                    'description': description,
                    'expires_at': expires_at,
                    'created_by': created_by,
                    'is_permanent': duration_hours is None,
                    'bypass_rate_limits': bypass_rate_limits,
                    'custom_rate_multiplier': custom_rate_multiplier,
                }
            )
            
            if not created:
                # Update existing entry
                whitelist_entry.is_active = True
                whitelist_entry.bypass_rate_limits = bypass_rate_limits
                whitelist_entry.custom_rate_multiplier = custom_rate_multiplier
                if duration_hours:
                    whitelist_entry.expires_at = timezone.now() + timedelta(hours=duration_hours)
                elif duration_hours is None:
                    whitelist_entry.is_permanent = True
                    whitelist_entry.expires_at = None
                whitelist_entry.save()
            
            return whitelist_entry
            
        except Exception as e:
            print_log(level='error', message=f"Failed to add whitelist entry: {str(e)}", exception_type='WhitelistError', file_path=__file__, line_number=cls.add_to_whitelist.__code__.co_firstlineno, view_name='WhiteList.add_to_whitelist')
            return None
    
    @classmethod
    def remove_from_whitelist(cls, ip_address=None, user=None):
        """Remove IP/User from whitelist"""
        filters = {}
        if ip_address:
            filters['ip_address'] = ip_address
        if user:
            filters['user'] = user
        
        if filters:
            cls.objects.filter(**filters).update(is_active=False)
            return True
        return False
    
    @classmethod
    def get_rate_multiplier(cls, ip_address, user=None):
        """Get custom rate multiplier for whitelisted IP/User"""
        is_whitelisted, whitelist_type, whitelist_entry = cls.is_whitelisted(ip_address, user)
        if is_whitelisted and whitelist_entry:
            return whitelist_entry.custom_rate_multiplier
        return 1.0

#############################################################################################
def rate_limit_response():
    return JsonResponse({
        'error': 'Rate limit exceeded. Please try again later.',
        'return': False
    }, status=429)
#############################################################################################
def blacklist_response():
    return JsonResponse({
        'error': 'Access denied. Your IP or account has been blacklisted.',
        'return': False
    }, status=403)

#############################################################################################
def custom_rate_limit(endpoint_name, limit=10, window_minutes=1):
    
    endpoint = RATE_LIMIT_ENDPOINTS.get(endpoint_name, {})
        
    limit = endpoint.get('limit', limit)
    window_minutes = endpoint.get('window_minutes', window_minutes)
    
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            ip_address = get_client_ip(request)
            user = request.user if request.user.is_authenticated else None
            
            # Check blacklist first
            is_blacklisted, blacklist_type = BlackList.is_blacklisted(ip_address, user)
            if is_blacklisted:
                print_log(level='warning', message=f"Blacklisted access attempt for {endpoint_name} - IP: {ip_address}, User: {user}, Type: {blacklist_type}", 
                         exception_type='BlacklistViolation', file_path=__file__, line_number=wrapper.__code__.co_firstlineno, view_name=func.__name__)
                return blacklist_response()
            
            # Check whitelist and adjust rate limits accordingly
            is_whitelisted, whitelist_type, whitelist_entry = WhiteList.is_whitelisted(ip_address, user)
            
            if is_whitelisted and whitelist_entry and whitelist_entry.bypass_rate_limits:
                # Skip rate limiting entirely for whitelisted entries with bypass enabled
                print_log(level='info', message=f"Rate limit bypassed for whitelisted {whitelist_type} - IP: {ip_address}, User: {user}", 
                         exception_type='WhitelistBypass', file_path=__file__, line_number=wrapper.__code__.co_firstlineno, view_name=func.__name__)
                return func(request, *args, **kwargs)
            
            # Apply custom rate multiplier for whitelisted users
            effective_limit = limit
            if is_whitelisted and whitelist_entry:
                effective_limit = int(limit * whitelist_entry.custom_rate_multiplier)
            
            # Check rate limit
            if RateLimit.check_rate_limit(ip_address, endpoint_name, effective_limit, window_minutes, user):
                print_log(level='warning', message=f"API rate limit exceeded for {endpoint_name}({endpoint}) - IP: {ip_address}, User: {user}", exception_type='RateLimitExceeded', file_path=__file__, line_number=wrapper.__code__.co_firstlineno, view_name=func.__name__)
                
                # Check if this IP has exceeded rate limits multiple times recently
                recent_violations = RateLimit.objects.filter(ip_address=ip_address, window_start__gte=timezone.now() - timedelta(hours=1)).count()

                if recent_violations >= 5:  # Auto-blacklist after 5 violations in 1 hour
                    BlackList.add_to_blacklist(ip_address=ip_address, user=user, reason='rate_limit_abuse', duration_hours=24,
                        description=f'Auto-blacklisted for excessive rate limit violations. it has blocked for 24 hours',
                    )
                    print_log(level='warning', message=f"Auto-blacklisted IP {ip_address} for rate limit abuse", 
                                exception_type='AutoBlacklist', file_path=__file__, line_number=wrapper.__code__.co_firstlineno, view_name=func.__name__)
                        
                return rate_limit_response()

            return func(request, *args, **kwargs)
        return wrapper
    return decorator
#############################################################################################
def api_rate_limit(func):
    return custom_rate_limit('api_general')(func)
##############################################################################################
def login_rate_limit(func):
    return custom_rate_limit('login_rate')(func)
##############################################################################################
def user_uuid_limit(func):
    return custom_rate_limit('user_uuid_rate')(func)
###############################################################################################
def api_search_rate_limit(func):
    return custom_rate_limit('api_search_rate')(func)
###############################################################################################
def api_user_auth_rate_limit(func):
    return custom_rate_limit('api_user_auth_rate')(func)