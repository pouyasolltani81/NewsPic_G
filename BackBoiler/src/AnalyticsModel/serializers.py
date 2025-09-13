from rest_framework import serializers

class AnalyticsOverviewSerializer(serializers.Serializer):
    total_requests = serializers.IntegerField()
    avg_response_time = serializers.FloatField()
    error_rate = serializers.FloatField()
    active_users = serializers.IntegerField()
    total_users = serializers.IntegerField()
    online_users = serializers.IntegerField()

class EndpointMetricsSerializer(serializers.Serializer):
    endpoint__path = serializers.CharField()
    endpoint__method = serializers.CharField()
    total_requests = serializers.IntegerField()
    avg_response_time = serializers.FloatField()
    error_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    unique_users = serializers.IntegerField()