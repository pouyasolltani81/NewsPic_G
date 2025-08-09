from django.db import models
import uuid
from app import settings
from UserModel.models import User
from django.utils import timezone

CREDENTIAL_TYPES = (
        ('app', 'App Credential'), # users have access to their own ASP by app credential only one app token is enough
        ('admin', 'Admin Credential'),  # users have access to their own ASP by admin credential need admin permission user
        ('user', 'User Credential'), # users have access to their own ASP by user credential need user_token
        ('none', 'No Credentail')
    )

def api_get_hash(message, len=16):
        import hashlib
        hash = hashlib.sha256(str(message).encode()).hexdigest()[:len]
        return hash + str(timezone.now().second) + str(timezone.now().microsecond)

# Connect only use by type='app', for type in ['user', 'admin'] use UserModel and AuthModel
class Connect(models.Model):    
    # if other app want to connect to this asp, they need to get the uuid and token
    # this token is used to verify the connection, if the token is not valid, the connection will be rejected.
    # token is randomly generated is unique for each asp
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    type = models.CharField(max_length=10, choices=CREDENTIAL_TYPES, default='app') # credential type
    name = models.CharField(max_length=20, default='')
    desc = models.CharField(max_length=255, default='')
    token = models.CharField(max_length=34, default= api_get_hash(str(timezone.now().second)), unique=True) # token is used to verify the connection, if the token is not valid, the connection will be rejected.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Connect'
        verbose_name_plural = 'Connects'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} - {self.token}"

    @classmethod
    def create_connect(cls, name='', desc='', type = 'app'):
        con = cls.objects.create(name=name, desc=desc, type=type)
        return con
    @classmethod
    def get_active_connects(cls):
        cons = cls.objects.filter(is_active=True)
        return cons