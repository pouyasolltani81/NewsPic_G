
from django.db import models
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.utils import timezone
from django.contrib.auth import authenticate
import uuid
from app.app_lib import get_phonenumber_start_with_zero
from django.contrib.sessions.models import Session
import json


class User(AbstractUser, PermissionsMixin):
    uuid = models.UUIDField(default=uuid.uuid4)
    is_active = models.BooleanField(default=True)
    username = models.CharField(max_length=150, default='', blank=True)
    email = models.EmailField(max_length=100, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    telegram_id = models.CharField(max_length=50, blank=True, null=True)
    last_activity_at =  models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'

    def __str__(self):
         return f'{self.email or self.phone_number} ({self.username})'
    
    def save(self, *args, **kwargs):
        # Convert empty string to None for email
        if self.email == '':
            self.email = None
        
        # Convert empty string to None for phone_number
        if self.phone_number == '':
            self.phone_number = None


        from AuthModel.models import UserAuth

        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from AuthModel.models import UserAuth
            UserAuth.objects.get_or_create(user=self)
            
    #############################################################################
    def auth(self):
        from AuthModel.models import UserAuth
        return UserAuth.objects.filter(user=self).first()
    
    ###########################################################################
    @classmethod
    def get_user_by_identifier(cls, identifier):
        """Get user by email or phone number"""
        # Check if identifier is email
        if '@' in identifier:
            return cls.objects.filter(email=identifier).first()
        else:
            cleaned_ph = get_phonenumber_start_with_zero(identifier)
            return cls.objects.filter(phone_number__in = cleaned_ph).first()
    #########################################################################
    @classmethod
    def get_user_auth(cls, identifier, password):
        """Authenticate user with email or phone number"""
        user = cls.get_user_by_identifier(identifier)

        if not user:
            return None, {'return': False, 'error': 'Invalid email or phone number.'}
        
        if not user.check_password(password):
            return None, {'return': False, 'error': 'Invalid password.'}
        
        if not user.is_active:
            return None, {'return': False, 'error': 'User is not active.'}
        
        if not user.auth().check_auth_expiration()['return']:
            return None, {'return': False, 'error': 'Token expired.'}
        
        return user, {'return': True}
    #########################################################################
    def get_user_asp_message(self):
        from SsoModel.models import AppServiceProvider
        asp = AppServiceProvider.objects.filter(name='Message', is_active=True).first()
        
        if not asp:
            return None, {'return': False, 'error': 'App Service Provider not found or inactive.'}
        return asp
    ###########################################################################
    def get_system_user(self):
        from CodeModel.models import SystemUser
        system_user = SystemUser.objects.filter(user=self).first()
        
        if not system_user:
            return None
        
        return system_user
    #########################################################################
    @classmethod
    def get_user_sessions(cls, user):
        """Get all active sessions for a specific user"""
        user_sessions = []
        
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
        for session in active_sessions:
            try:
                session_data = session.get_decoded()
                # Check if this session belongs to the user
                if str(user.pk) == str(session_data.get('_auth_user_id')):
                    user_sessions.append({
                        'session_key': session.session_key,
                        'expire_date': session.expire_date,
                        'data': session_data,
                        'ip_address': session_data.get('ip_address', 'Unknown'),
                        'user_agent': session_data.get('user_agent', 'Unknown'),
                    })
            except:
                # Skip sessions that can't be decoded
                continue
        
        return user_sessions
    ##############################################################################
    @property
    def is_online(self):
        from datetime import timedelta
        
        if not self.last_activity_at:
            return False
        
        # Define activity threshold (5 minutes)
        activity_threshold = timezone.now() - timedelta(minutes=5)
        
        # Check if user was active recently AND has an active session
        return self.last_activity_at >= activity_threshold
    
    ##############################################################################
    def get_or_fetch_telegram_id(self):
        """Get telegram_id from database or fetch from service if not available"""
        if self.telegram_id:
            return self.telegram_id
        
        if not self.phone_number:
            return None
        
        try:
            # Import here to avoid circular imports
            from .services import GetTelegramInfo
            from django.test import RequestFactory
            
            # Create a mock request to call the service
            factory = RequestFactory()
            request = factory.post('/GetTelegramInfo/', {
                'phone_number': self.phone_number
            }, content_type='application/json')
            
            # Call the service function directly
            response = GetTelegramInfo(request)
            
            if response.status_code == 200:
                data = json.loads(response.content.decode('utf-8'))
                if data.get('return') and data.get('user'):
                    telegram_id = data['user'].get('telegram_id') or data['user'].get('chat_id')
                    if telegram_id:
                        self.telegram_id = str(telegram_id)
                        self.save(update_fields=['telegram_id'])
                        return self.telegram_id
            
            return None
            
        except Exception as e:
            print(f"Error fetching telegram_id for user {self.id}: {e}")
            return None