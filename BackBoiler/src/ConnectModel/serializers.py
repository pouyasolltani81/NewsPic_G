from rest_framework import serializers
from .models import Connect

class ConnectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Connect
        fields = ['id', 'uuid', 'type', 'name', 'desc', 'token', 'created_at', 'updated_at', 'is_active']
        read_only_fields = ['created_at', 'updated_at']
