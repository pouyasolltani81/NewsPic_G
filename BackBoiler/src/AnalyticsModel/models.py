from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.postgres.fields import JSONField

User = get_user_model()

class APIEndpoint(models.Model):
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    view_name = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['path', 'method']  # This ensures path+method is unique
        indexes = [
            models.Index(fields=['path', 'method']),
        ]
class APIRequest(models.Model):
    MAX_RECORDS = 1_000_000

    endpoint = models.ForeignKey(APIEndpoint, on_delete=models.CASCADE, related_name='requests')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    response_time = models.FloatField()  
    status_code = models.IntegerField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    request_body_size = models.IntegerField(default=0)
    response_body_size = models.IntegerField(default=0)

    device_type = models.CharField(max_length=50, null=True)
    browser = models.CharField(max_length=100, null=True)
    os = models.CharField(max_length=100, null=True)

    country = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)

    query_params = models.JSONField(default=dict, blank=True)
    headers = models.JSONField(default=dict, blank=True)

    error_message = models.TextField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['endpoint', 'timestamp']),
            models.Index(fields=['status_code']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total = APIRequest.objects.count()
        if total > self.MAX_RECORDS:
            excess = total - self.MAX_RECORDS
            oldest_ids = (
                APIRequest.objects.order_by("timestamp")
                .values_list("id", flat=True)[:excess]
            )
            APIRequest.objects.filter(id__in=oldest_ids).delete()

class UserSession(models.Model):
    MAX_RECORDS = 100_000

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='AnalyticsModel_sessions')
    session_key = models.CharField(max_length=40, unique=True)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    is_active = models.BooleanField(default=True)

    page_views = models.IntegerField(default=0)
    api_calls = models.IntegerField(default=0)
    total_response_time = models.FloatField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['last_activity']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total = UserSession.objects.count()
        if total > self.MAX_RECORDS:
            excess = total - self.MAX_RECORDS
            oldest_ids = (
                UserSession.objects.order_by("start_time")
                .values_list("id", flat=True)[:excess]
            )
            UserSession.objects.filter(id__in=oldest_ids).delete()
            
            
class SystemMetrics(models.Model):
    MAX_RECORDS = 100_000  

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    cpu_usage = models.FloatField()
    memory_usage = models.FloatField()       # % used
    total_memory_gb = models.FloatField()    # total RAM in GB
    
    # GPU fields
    gpu_memory_usage = models.FloatField(null=True, blank=True)      # % used
    gpu_total_memory_gb = models.FloatField(null=True, blank=True)   # total GPU memory in GB
    gpu_name = models.CharField(max_length=255, null=True, blank=True)  # GPU model name
    gpu_temperature = models.FloatField(null=True, blank=True)       # GPU temperature in Celsius
    
    disk_usage = models.FloatField()
    active_connections = models.IntegerField()
    database_connections = models.IntegerField()
    cache_hit_rate = models.FloatField(null=True)
    queue_size = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total = SystemMetrics.objects.count()
        if total > self.MAX_RECORDS:
            excess = total - self.MAX_RECORDS
            oldest_ids = (
                SystemMetrics.objects.order_by("timestamp")
                .values_list("id", flat=True)[:excess]
            )
            SystemMetrics.objects.filter(id__in=oldest_ids).delete()

    @property
    def gpu_free_memory_gb(self):
        """Calculate free GPU memory in GB"""
        if self.gpu_total_memory_gb and self.gpu_memory_usage is not None:
            return self.gpu_total_memory_gb * (1 - self.gpu_memory_usage / 100)
        return None

    @property
    def gpu_free_memory_percent(self):
        """Calculate free GPU memory percentage"""
        if self.gpu_memory_usage is not None:
            return 100 - self.gpu_memory_usage
        return None

    @property
    def system_free_memory_gb(self):
        """Calculate free system memory in GB"""
        if self.total_memory_gb and self.memory_usage is not None:
            return self.total_memory_gb * (1 - self.memory_usage / 100)
        return None

    @property
    def system_free_memory_percent(self):
        """Calculate free system memory percentage"""
        if self.memory_usage is not None:
            return 100 - self.memory_usage
        return None