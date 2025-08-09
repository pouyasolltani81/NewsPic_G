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
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='error')
    message = models.TextField(default='')
    exception_type = models.CharField(max_length=255, default='')
    stack_trace = models.TextField(default='')
    file_path = models.CharField(max_length=255, default='')
    line_number = models.IntegerField(default=0)
    view_name = models.CharField(max_length=255, null=True, blank=True)
    
    objects =  LogManager(db_name = 'Logs', record_limit=1000)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.level}: {self.message}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if Log.objects.using(Log.objects.db_name).count() > Log.objects.record_limit:
            Log.objects.delete_oldest()

    