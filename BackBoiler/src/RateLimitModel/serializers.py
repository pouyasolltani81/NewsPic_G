from rest_framework import serializers
from django.utils import timezone
from .models import RateLimit, BlackList, WhiteList
from UserModel.models import User


class RateLimitSerializer(serializers.ModelSerializer):
    """Serializer for RateLimit model"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    is_active = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = RateLimit
        fields = ['id', 'ip_address', 'user', 'user_username', 'endpoint', 'request_count', 'window_start', 'is_active', 'time_remaining',
            'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_username', 'is_active', 'time_remaining']
    
    def get_is_active(self, obj):
        """Check if the rate limit window is still active"""
        from .models import RATE_LIMIT_ENDPOINTS
        endpoint_config = RATE_LIMIT_ENDPOINTS.get(obj.endpoint, {'window_minutes': 1})
        window_minutes = endpoint_config['window_minutes']
        
        window_end = obj.window_start + timezone.timedelta(minutes=window_minutes)
        return timezone.now() < window_end
    
    def get_time_remaining(self, obj):
        """Get remaining time in seconds for the current window"""
        from .models import RATE_LIMIT_ENDPOINTS
        endpoint_config = RATE_LIMIT_ENDPOINTS.get(obj.endpoint, {'window_minutes': 1})
        window_minutes = endpoint_config['window_minutes']
        
        window_end = obj.window_start + timezone.timedelta(minutes=window_minutes)
        remaining = window_end - timezone.now()
        
        return max(0, int(remaining.total_seconds())) if remaining.total_seconds() > 0 else 0


class BlackListSerializer(serializers.ModelSerializer):
    """Serializer for BlackList model"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    is_expired = serializers.ReadOnlyField()
    time_remaining = serializers.SerializerMethodField()
    blacklist_type_display = serializers.CharField(source='get_blacklist_type_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = BlackList
        fields = ['id', 'ip_address', 'user', 'user_username', 'blacklist_type', 'blacklist_type_display', 'reason',
            'reason_display', 'description', 'is_permanent', 'expires_at', 'is_expired', 'time_remaining', 'violation_count',
            'last_violation', 'created_by', 'is_active', 'created_at', 'updated_at' ]
        read_only_fields = [
            'id', 'is_expired', 'time_remaining', 'user_username', 
            'blacklist_type_display', 'reason_display', 'created_at', 'updated_at'
        ]
    
    def get_time_remaining(self, obj):
        """Get remaining time in seconds until blacklist expires"""
        if obj.is_permanent or not obj.expires_at:
            return None
        
        remaining = obj.expires_at - timezone.now()
        return max(0, int(remaining.total_seconds())) if remaining.total_seconds() > 0 else 0
    
    def validate(self, data):
        """Validate blacklist data"""
        if not data.get('ip_address') and not data.get('user'):
            raise serializers.ValidationError("Either ip_address or user must be provided.")
        
        if data.get('is_permanent') and data.get('expires_at'):
            raise serializers.ValidationError("Permanent blacklist cannot have expiration date.")
        
        if not data.get('is_permanent') and not data.get('expires_at'):
            raise serializers.ValidationError("Non-permanent blacklist must have expiration date.")
        
        return data


class WhiteListSerializer(serializers.ModelSerializer):
    """Serializer for WhiteList model"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    is_expired = serializers.ReadOnlyField()
    time_remaining = serializers.SerializerMethodField()
    whitelist_type_display = serializers.CharField(source='get_whitelist_type_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = WhiteList
        fields = ['id', 'ip_address', 'user', 'user_username', 'whitelist_type', 'whitelist_type_display', 'reason', 'reason_display', 'description',
            'is_permanent', 'expires_at', 'is_expired', 'time_remaining', 'usage_count', 'last_used',  'created_by', 'is_active', 'bypass_rate_limits',
            'custom_rate_multiplier', 'created_at', 'updated_at']
        read_only_fields = [
            'id', 'is_expired', 'time_remaining', 'user_username', 'whitelist_type_display', 'reason_display', 'usage_count', 
            'last_used', 'created_at', 'updated_at' ]
    
    def get_time_remaining(self, obj):
        """Get remaining time in seconds until whitelist expires"""
        if obj.is_permanent or not obj.expires_at:
            return None
        
        remaining = obj.expires_at - timezone.now()
        return max(0, int(remaining.total_seconds())) if remaining.total_seconds() > 0 else 0
    
    def validate(self, data):
        """Validate whitelist data"""
        if not data.get('ip_address') and not data.get('user'):
            raise serializers.ValidationError("Either ip_address or user must be provided.")
        
        if data.get('is_permanent') and data.get('expires_at'):
            raise serializers.ValidationError("Permanent whitelist cannot have expiration date.")
        
        if not data.get('is_permanent') and not data.get('expires_at'):
            raise serializers.ValidationError("Non-permanent whitelist must have expiration date.")
        
        custom_rate_multiplier = data.get('custom_rate_multiplier', 1.0)
        if custom_rate_multiplier <= 0:
            raise serializers.ValidationError("Custom rate multiplier must be greater than 0.")
        
        return data

