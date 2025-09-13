from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'uuid', 'email', 'phone_number', 'username', 'is_active', 'is_staff', 'is_superuser', 'is_online',
                  'last_activity_at', 'date_joined', 'last_login']
        read_only_fields = ['id', 'is_active', 'is_online']
    