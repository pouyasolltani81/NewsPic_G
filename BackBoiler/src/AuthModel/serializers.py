from rest_framework import serializers
from .models import UserAuth
from UserModel.serializers import UserSerializer

class UserAuthSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    class Meta:
        model = UserAuth
        fields = ['id', 'user', 'token', 'created_at', 'expired_at']
        read_only_fields = ['id', 'created_at']
    
    