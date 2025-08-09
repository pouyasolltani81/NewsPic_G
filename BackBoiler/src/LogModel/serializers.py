from rest_framework import serializers
from .models import Log

class LogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Log
        fields = ['id', 'timestamp', 'user', 'level', 'message', 'exception_type', 'file_path', 'line_number', 'view_name']