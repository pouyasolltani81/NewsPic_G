from django.db import models
from django.utils import timezone
from datetime import timedelta
from app import settings
from UserModel.models import User
import hashlib
from functools import wraps
from django.http import JsonResponse

def api_get_hash(message, len=32):
    hash = hashlib.sha256(str(message).encode()).hexdigest()[:len]
    return hash

def app_credential(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        
        app_token = request.headers.get('Authorization')

        if not app_token:
            return JsonResponse({'error': 'Access denied: app token is missing.', 'return': False})

        # check authorization header with app token
        from ConnectModel.models import Connect
        
        cons = Connect.get_active_connects().filter(token=app_token, type='app')
        
        if cons.count() == 0:
            return JsonResponse({'error': 'Access denied: no active connection credential', 'return': False})
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
#######################################################################
def admin_credential(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        auth_token = request.headers.get('Authorization')
    
        if not auth_token:
            return JsonResponse({'error': 'User not authenticated and auth token is missing.', 'return': False})
        
        try:
            ua = UserAuth.objects.get(token=auth_token)
            if not ua.user.is_superuser:
                return JsonResponse({'error': 'Access denied: user is not admin.', 'return': False})
        except Exception as e:
            return JsonResponse({'error': 'Invalid Auth token: ' + str(e), 'return': False})
        
        exp_at = ua.check_auth_expiration()
        if not exp_at['return']:
            return JsonResponse({'error': 'Auth token expired.', 'return': False})

        request.user = ua.user
        return view_func(request, *args, **kwargs)
    
    return wrapper
    
#######################################################################
def user_credential(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        auth_token = request.headers.get('Authorization')

        if not auth_token:
            return JsonResponse({'error': 'User not authenticated and auth token is missing.', 'return': False})
        
        try:
            ua = UserAuth.objects.get(token=auth_token)
            
        except Exception as e:
            return JsonResponse({'error': 'Invalid Auth token: ' + str(e), 'return': False})
        
        exp_at = ua.check_auth_expiration()
        if not exp_at['return']:
            return JsonResponse({'error': 'Auth token expired.', 'return': False})

        request.user = ua.user
        return view_func(request, *args, **kwargs)
    
    return wrapper
    
#######################################################################
class UserAuth(models.Model):
    user = models.OneToOneField(User, null=False, blank=False, related_name='user_auth', on_delete=models.CASCADE)
    token = models.CharField(max_length=32, null=False, blank=False) # to get service

    created_at = models.DateTimeField(auto_now_add=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'User Auth'
        verbose_name_plural = 'User Auth'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user}'
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = api_get_hash(f'{self.user.id}/{timezone.now().second}/token', len=32)
            self.expired_at = timezone.now() + timedelta(hours=720)

        super().save(*args, **kwargs)
    
    def check_auth_expiration(self):
        if self.expired_at < timezone.now():
            return {'return':False, 'error':'Token Expired.'}
        
        return {'return':True, 'message':'Token is valid.'}
