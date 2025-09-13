from django.db import models
from django.utils import timezone
from UserModel.models import User

LEVEL_CHOICES = [
    ('error', 'Error'),
    ('warning', 'Warning'),
    ('urgent error', 'Urgent Error'),
    ('return', 'Return'),
    ('info', 'Info'),
]
class LogManager(models.Manager):
    def __init__(self, db_name, record_limit):
        self.db_name = db_name
        self.record_limit = record_limit
        super().__init__()

    def using(self, alias):
        return self.get_queryset().using(alias)
    
    def delete_oldest(self):
        cnt = Log.objects.using(self.db_name).count()
        oldest_instances = Log.objects.using(self.db_name).order_by('timestamp')[:100]
        for instance in oldest_instances:
            instance.delete(using = self.db_name)

class Log(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
        ('debug', 'Debug'),
    ]
    
    ERROR_TYPE_CHOICES = [
        ('none', 'None'),
        ('validation', 'Validation Error'),
        ('authentication', 'Authentication Error'),
        ('permission', 'Permission Error'),
        ('not_found', 'Not Found'),
        ('server', 'Server Error'),
        ('database', 'Database Error'),
        ('external_api', 'External API Error'),
        ('business_logic', 'Business Logic Error'),
        ('unknown', 'Unknown Error'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE , null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='error')
    message = models.TextField(default='')
    exception_type = models.CharField(max_length=255, default='')
    stack_trace = models.TextField(default='')
    file_path = models.CharField(max_length=255, default='')  # Keep existing field for filename
    full_file_path = models.CharField(max_length=500, default='')  # New field for full path
    line_number = models.IntegerField(default=0)
    view_name = models.CharField(max_length=255, null=True, blank=True)
    api_endpoint = models.CharField(max_length=255, default='')  # New field for API endpoint
    http_method = models.CharField(max_length=10, default='')  # GET, POST, etc.
    is_error = models.BooleanField(default=False)  # New field to indicate if it's an error
    error_category = models.CharField(max_length=50, choices=ERROR_TYPE_CHOICES, default='none')  # New field for error type
    request_path = models.CharField(max_length=500, default='')  # Full request path
    user_ip = models.GenericIPAddressField(null=True, blank=True)  # User IP address
    user_agent = models.TextField(default='')  # Browser/client info
    
    objects = LogManager(db_name='Logs', record_limit=1000)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['level', '-timestamp']),
            models.Index(fields=['is_error', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.level}: {self.message}"
    
    def save(self, *args, **kwargs):
        # Auto-set is_error based on level
        if self.level in ['error', 'critical']:
            self.is_error = True
        
        super().save(*args, **kwargs)
        
        # Clean up old logs
        if Log.objects.using(Log.objects.db_name).count() > Log.objects.record_limit:
            Log.objects.delete_oldest()