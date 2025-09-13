from rest_framework import serializers
from .models import Log

class LogSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    error_category_display = serializers.CharField(source='get_error_category_display', read_only=True)
    
    class Meta:
        model = Log
        fields = [
            'id', 'user', 'user_display', 'timestamp', 'level', 'message',
            'exception_type', 'stack_trace', 'file_path', 'full_file_path',
            'line_number', 'view_name', 'api_endpoint', 'http_method',
            'is_error', 'error_category', 'error_category_display',
            'request_path', 'user_ip', 'user_agent'
        ]
    
    def get_user_display(self, obj):
        if obj.user:
            return f"{obj.user.username} ({obj.user.email})"
        return "Anonymous"