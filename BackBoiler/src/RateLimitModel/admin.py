# Register your models here.
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.forms import TextInput, Textarea
from django.utils import timezone
from datetime import timedelta
from .models import RateLimit, BlackList, WhiteList


class RateLimitAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'ip_address',
        'user',
        'endpoint',
        'request_count',
        'window_start',
        'status',
        'created_at'
    ]
    
    
    search_fields = [
        'ip_address',
        'endpoint',
        'user__username',
        'user__email'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    ordering = ['-created_at']
    list_per_page = 25
    
    actions = ['reset_rate_limits', 'delete_expired']

    def status(self, obj):
        """Show detailed status of rate limit based on endpoint configuration"""
        from django.utils import timezone
        from .models import RATE_LIMIT_ENDPOINTS
        from django.utils.html import format_html
        
        now = timezone.now()
        
        # Get endpoint configuration
        endpoint_config = RATE_LIMIT_ENDPOINTS.get(obj.endpoint, {
            'limit': 50, 
            'window_minutes': 60
        })
        
        limit = endpoint_config['limit']
        window_minutes = endpoint_config['window_minutes']
        
        # Calculate window age in minutes
        window_age = (now - obj.window_start).total_seconds() / 60
        
        # Check if window has expired
        if window_age > window_minutes:
            remaining_time = 0
            status_text = "Expired"
            color = "red"
        else:
            remaining_time = window_minutes - window_age
            usage_percentage = (obj.request_count / limit) * 100
            
            if obj.request_count >= limit:
                status_text = f"Blocked ({obj.request_count}/{limit})"
                color = "red"
            elif usage_percentage >= 80:
                status_text = f"High ({obj.request_count}/{limit})"
                color = "orange"
            elif usage_percentage >= 50:
                status_text = f"Medium ({obj.request_count}/{limit})"
                color = "#ff9800"
            else:
                status_text = f"Active ({obj.request_count}/{limit})"
                color = "green"
        
        # Format remaining time
        if remaining_time > 60:
            time_str = f"{remaining_time/60:.1f}h"
        elif remaining_time > 1:
            time_str = f"{remaining_time:.0f}m"
        elif remaining_time > 0:
            time_str = f"{remaining_time*60:.0f}s"
        else:
            time_str = "0s"
        
        if remaining_time > 0:
            return format_html(
                '<span style="color: {};">{}</span><br><small>Resets in: {}</small>',
                color, status_text, time_str
            )
        else:
            return format_html('<span style="color: {};">{}</span>', color, status_text)

    status.short_description = 'Status'


    def reset_rate_limits(self, request, queryset):
        """Reset selected rate limits"""
        for obj in queryset:
            obj.request_count = 0
            obj.window_start = timezone.now()
            obj.save()
        
        self.message_user(request, f'Reset {queryset.count()} rate limits.')
    
    reset_rate_limits.short_description = "Reset selected rate limits"

    def delete_expired(self, request, queryset):
        """Delete expired rate limit records"""
        one_hour_ago = timezone.now() - timedelta(hours=1)
        expired = queryset.filter(window_start__lt=one_hour_ago)
        count = expired.count()
        expired.delete()
        
        self.message_user(request, f'Deleted {count} expired records.')
    
    delete_expired.short_description = "Delete expired records"
################################################################################
class BlackListAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'get_target_info', 
        'blacklist_type', 
        'reason', 
        'violation_count',
        'get_status',
        'get_expires_info',
        'created_by',
        'created_at'
    ]
    
    search_fields = [
        'ip_address',
        'user__username',
        'user__email',
        'description',
        'reason'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'last_violation',
        'violation_count'
    ]
    
    fieldsets = (
        ('Target Information', {
            'fields': ('ip_address', 'user', 'blacklist_type')
        }),
        ('Blacklist Details', {
            'fields': ('reason', 'description', 'created_by')
        }),
        ('Duration Settings', {
            'fields': ('is_permanent', 'expires_at', 'is_active')
        }),
        ('Tracking Information', {
            'fields': ('violation_count', 'last_violation', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '40'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 60})},
    }
    
    actions = ['activate_blacklist', 'deactivate_blacklist', 'extend_blacklist', 'make_permanent']
    
    def get_target_info(self, obj):
        """Display target information based on blacklist type"""
        if obj.blacklist_type == 'ip':
            return format_html('<strong>IP:</strong> {}', obj.ip_address)
        elif obj.blacklist_type == 'user':
            return format_html('<strong>User:</strong> {}', obj.user.username if obj.user else 'N/A')
        else:  # both
            return format_html(
                '<strong>IP:</strong> {}<br><strong>User:</strong> {}',
                obj.ip_address,
                obj.user.username if obj.user else 'N/A'
            )
    get_target_info.short_description = 'Target'
    get_target_info.allow_tags = True
    
    def get_status(self, obj):
        """Display current status with color coding"""
        if not obj.is_active:
            return format_html('<span style="color: gray;">Inactive</span>')
        elif obj.is_expired:
            return format_html('<span style="color: orange;">Expired</span>')
        elif obj.is_permanent:
            return format_html('<span style="color: red; font-weight: bold;">Permanent</span>')
        else:
            return format_html('<span style="color: green;">Active</span>')
    get_status.short_description = 'Status'
    get_status.allow_tags = True
    
    def get_expires_info(self, obj):
        """Display expiration information"""
        if obj.is_permanent:
            return format_html('<span style="color: red;">Permanent</span>')
        elif obj.expires_at:
            if obj.expires_at > timezone.now():
                return format_html(
                    '<span style="color: orange;">{}</span>',
                    obj.expires_at.strftime('%Y-%m-%d %H:%M')
                )
            else:
                return format_html('<span style="color: gray;">Expired</span>')
        return 'No expiration'
    get_expires_info.short_description = 'Expires At'
    get_expires_info.allow_tags = True
    
    def activate_blacklist(self, request, queryset):
        """Activate selected blacklist entries"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} blacklist entries activated.')
    activate_blacklist.short_description = "Activate selected blacklist entries"
    
    def deactivate_blacklist(self, request, queryset):
        """Deactivate selected blacklist entries"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} blacklist entries deactivated.')
    deactivate_blacklist.short_description = "Deactivate selected blacklist entries"
    
    def extend_blacklist(self, request, queryset):
        """Extend blacklist by 24 hours"""
        from datetime import timedelta
        count = 0
        for obj in queryset:
            if not obj.is_permanent:
                if obj.expires_at:
                    obj.expires_at = max(obj.expires_at, timezone.now()) + timedelta(hours=24)
                else:
                    obj.expires_at = timezone.now() + timedelta(hours=24)
                obj.is_active = True
                obj.save()
                count += 1
        self.message_user(request, f'{count} blacklist entries extended by 24 hours.')
    extend_blacklist.short_description = "Extend selected entries by 24 hours"
    
    def make_permanent(self, request, queryset):
        """Make selected blacklist entries permanent"""
        updated = queryset.update(is_permanent=True, expires_at=None, is_active=True)
        self.message_user(request, f'{updated} blacklist entries made permanent.')
    make_permanent.short_description = "Make selected entries permanent"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
#################################################################################################
class WhiteListAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_target_info', 'whitelist_type', 'reason', 'get_rate_settings', 'usage_count', 'get_status', 'get_expires_info','created_by',
        'created_at' ]
    
    search_fields = ['ip_address', 'user__username', 'user__email', 'description', 'reason']
    
    readonly_fields = ['created_at', 'updated_at', 'usage_count', 'last_used']
    
    fieldsets = (
        ('Target Information', {
            'fields': ('ip_address', 'user', 'whitelist_type')
        }),
        ('Whitelist Details', {
            'fields': ('reason', 'description', 'created_by')
        }),
        ('Duration Settings', {
            'fields': ('is_permanent', 'expires_at', 'is_active')
        }),
        ('Rate Limit Settings', {
            'fields': ('bypass_rate_limits', 'custom_rate_multiplier'),
            'description': 'Configure how rate limiting applies to this whitelist entry'
        }),
        ('Usage Tracking', {
            'fields': ('usage_count', 'last_used', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '40'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 60})},
    }
    
    actions = ['activate_whitelist', 'deactivate_whitelist', 'extend_whitelist', 'make_permanent', 'enable_bypass', 'disable_bypass']
    
    def get_target_info(self, obj):
        """Display target information based on whitelist type"""
        if obj.whitelist_type == 'ip':
            return format_html('<strong>IP:</strong> {}', obj.ip_address)
        elif obj.whitelist_type == 'user':
            return format_html('<strong>User:</strong> {}', obj.user.username if obj.user else 'N/A')
        else:  # both
            return format_html(
                '<strong>IP:</strong> {}<br><strong>User:</strong> {}',
                obj.ip_address,
                obj.user.username if obj.user else 'N/A'
            )
    get_target_info.short_description = 'Target'
    get_target_info.allow_tags = True
    
    def get_rate_settings(self, obj):
        """Display rate limit settings"""
        if obj.bypass_rate_limits:
            return format_html('<span style="color: green; font-weight: bold;">Bypass All</span>')
        else:
            multiplier = obj.custom_rate_multiplier
            if multiplier == 1.0:
                return format_html('<span style="color: blue;">Normal Limits</span>')
            elif multiplier > 1.0:
                return format_html('<span style="color: orange;">{}x Limits</span>', multiplier)
            else:
                return format_html('<span style="color: red;">{}x Limits</span>', multiplier)
    get_rate_settings.short_description = 'Rate Settings'
    get_rate_settings.allow_tags = True
    
    def get_status(self, obj):
        """Display current status with color coding"""
        if not obj.is_active:
            return format_html('<span style="color: gray;">Inactive</span>')
        elif obj.is_expired:
            return format_html('<span style="color: orange;">Expired</span>')
        elif obj.is_permanent:
            return format_html('<span style="color: green; font-weight: bold;">Permanent</span>')
        else:
            return format_html('<span style="color: green;">Active</span>')
    get_status.short_description = 'Status'
    get_status.allow_tags = True
    
    def get_expires_info(self, obj):
        """Display expiration information"""
        if obj.is_permanent:
            return format_html('<span style="color: green;">Permanent</span>')
        elif obj.expires_at:
            if obj.expires_at > timezone.now():
                return format_html(
                    '<span style="color: orange;">{}</span>',
                    obj.expires_at.strftime('%Y-%m-%d %H:%M')
                )
            else:
                return format_html('<span style="color: gray;">Expired</span>')
        return 'No expiration'
    get_expires_info.short_description = 'Expires At'
    get_expires_info.allow_tags = True
    
    def activate_whitelist(self, request, queryset):
        """Activate selected whitelist entries"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} whitelist entries activated.')
    activate_whitelist.short_description = "Activate selected whitelist entries"
    
    def deactivate_whitelist(self, request, queryset):
        """Deactivate selected whitelist entries"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} whitelist entries deactivated.')
    deactivate_whitelist.short_description = "Deactivate selected whitelist entries"
    
    def extend_whitelist(self, request, queryset):
        """Extend whitelist by 24 hours"""
        from datetime import timedelta
        count = 0
        for obj in queryset:
            if not obj.is_permanent:
                if obj.expires_at:
                    obj.expires_at = max(obj.expires_at, timezone.now()) + timedelta(hours=24)
                else:
                    obj.expires_at = timezone.now() + timedelta(hours=24)
                obj.is_active = True
                obj.save()
                count += 1
        self.message_user(request, f'{count} whitelist entries extended by 24 hours.')
    extend_whitelist.short_description = "Extend selected entries by 24 hours"
    
    def make_permanent(self, request, queryset):
        """Make selected whitelist entries permanent"""
        updated = queryset.update(is_permanent=True, expires_at=None, is_active=True)
        self.message_user(request, f'{updated} whitelist entries made permanent.')
    make_permanent.short_description = "Make selected entries permanent"
    
    def enable_bypass(self, request, queryset):
        """Enable rate limit bypass for selected entries"""
        updated = queryset.update(bypass_rate_limits=True)
        self.message_user(request, f'{updated} whitelist entries now bypass rate limits.')
    enable_bypass.short_description = "Enable rate limit bypass"
    
    def disable_bypass(self, request, queryset):
        """Disable rate limit bypass for selected entries"""
        updated = queryset.update(bypass_rate_limits=False)
        self.message_user(request, f'{updated} whitelist entries no longer bypass rate limits.')
    disable_bypass.short_description = "Disable rate limit bypass"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    
admin.site.register(BlackList, BlackListAdmin)
admin.site.register(RateLimit, RateLimitAdmin)
admin.site.register(WhiteList, WhiteListAdmin)