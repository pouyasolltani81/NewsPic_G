from rest_framework import serializers
from .models import AppServiceProvider, SsoUser

class AppServiceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppServiceProvider
        fields = ['id', 'name', 'desc', 'app_uuid', 'app_token', 'route_config', 'credential_type', 'is_active', 'create_at']
        read_only_fields = ['create_at']

class SsoUserSerializer(serializers.ModelSerializer):
    asp = AppServiceProviderSerializer()
    class Meta:
        model = SsoUser
        fields = ['id', 'user', 'asp', 'asp_user_uuid', 'asp_user_token', 'is_active', 'last_access_at', 'create_at']
        read_only_fields = ['last_access_at', 'create_at']