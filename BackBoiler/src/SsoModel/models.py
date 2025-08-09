from django.db import models
from UserModel.models import User
import uuid
import json

# AppServiceProvider is a model that represents a service provider (independent application) in the SSO system (single sign on)
# for replica of the specified service provider name should be the same, else providers are considered different.
# each user can have multiple service providers but only 1 replica of each service provider
# each service provider can have multiple users
def default_route_config():
    return {"machine_name":"hetz no.1", "ip": "", "http_url": "", "https_url": ""}

CREDENTIAL_TYPES = (
            ('app', 'App Credential'), # users have access to their own ASP by app credential only one app token is enough
            ('admin', 'Admin Credential'), # users have access to their own ASP by admin credential need admin permission user
            ('user', 'User Credential'), # users have access to their own ASP by user credential need user_token
            ('none', 'No Credentail') # users have access to their own ASP by no credential
        )

# The destination service core of the app service provider
SERVICE_CORE = (
    ('message', 'Message Core'),
    ('exchange', 'Exchange Core'),
    ('user_management', 'User Management Core'),
    ('market', 'Market Core'),
    ('news', 'News Core'),
)

class AppServiceProvider(models.Model):
    # name of the service provider, if there is provider shards, 'name' should be the same for all shards
    name = models.CharField(max_length=100)
    desc = models.TextField(default='')
    
    # id of the service provider (independent application) in the SSO system (single sign on)
    app_uuid = models.UUIDField(default=uuid.uuid4, editable=True, null=False, blank=False)
    # app token of the service provider 
    app_token = models.CharField(max_length=32, null=False, blank=False)
    # url of the service provider 
    route_config = models.JSONField(default=default_route_config)
    service_core = models.CharField(max_length=20, choices=SERVICE_CORE, default='message')
    credential_type = models.CharField(max_length=20, choices=CREDENTIAL_TYPES, default='app')
    is_active = models.BooleanField(default=True)
    create_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'App Service Provider'
        verbose_name_plural = 'App Service Providers'
        ordering = ['name']

    def url(self):
        
        r_url = self.route_config['https_url']
        if not r_url:
            r_url = self.route_config['http_url']
        
        return r_url
    
    @classmethod
    def create_asp(cls, app_uuid, name, desc, app_token, route_config, credential_type):
        asp = cls.objects.create(app_uuid=app_uuid, name=name, desc=desc, app_token=app_token, route_config=route_config,  
                                 credential_type=credential_type)
        return asp

    def change_activate(self):
        self.is_active = not self.is_active
        self.save()

    @classmethod
    def get_shards_asps(cls, name):
        return cls.objects.filter(name=name)

# each user can have multiple service providers with different app_user_uuid
class SsoUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    asp = models.ForeignKey(AppServiceProvider, on_delete=models.CASCADE)
    # app service provider user uuid
    asp_user_uuid = models.UUIDField(blank=False, null=False, default=uuid.uuid4, editable=True)
    # app service provider token
    asp_user_token = models.CharField(max_length=32, null=False, blank=False)

    is_active = models.BooleanField(default=True)

    last_access_at = models.DateTimeField(auto_now=True)
    create_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.user} - {self.asp} - {self.asp_user_uuid}'
    class Meta:
        unique_together = ['user', 'asp']

    
        
    @classmethod
    def create_sso_user(cls, user, asp, asp_user_uuid, asp_user_token):
        
        try:
            sso_user = cls.objects.create(user=user, asp=asp, asp_user_uuid=asp_user_uuid, 
                            asp_user_token=asp_user_token)
            return sso_user
        except Exception as e:
            return None
        
    ##############################################################
    @classmethod
    def create_asps_user(cls, user, asp_user_email, asp_user_password):
        # this is backboiler test case for show service_core usability
        
        from .connects import asp_service_register_by_email

        try:
            asps = AppServiceProvider.objects.filter(is_active=True)

            ## Put Load Balance or Sharding Here
            asps_user = []

            for asp in asps:
                try:
                    if asp.service_core in ['market', 'news']:
                        res = asp_service_register_by_email(asp=asp, email_=asp_user_email, pass_=asp_user_password)
                    
                        if res and res['return']:
                            asp_user_uuid = res['asp_user']['user']['uuid']
                            asp_user_token = res['asp_user']['auth']['user_token']

                            sso_asp_user = cls.create_sso_user(user=user, asp=asp, asp_user_uuid=asp_user_uuid, asp_user_token=asp_user_token)
                            if sso_asp_user:
                                asps_user.append(sso_asp_user)
                        
                except Exception as e:
                    print(f'create_asps_user: {asp.name}-{asp.app_uuid}: {e}')
                    continue

            return asps_user
        except Exception as e:
            print('create_asps_user:' + str(e))
            return asps_user
    ###############################################################
    def change_activate(self):
        self.is_active = not self.is_active
        self.save()
    #############################################################
    def get_user_asps(self):
        return SsoUser.objects.filter(user=self.user)
    #############################################################
    def get_user_asp_by_uuid(self, asp_user_uuid):
        return SsoUser.objects.filter(user=self.user, asp_user_uuid=asp_user_uuid).first()
    #############################################################
    def get_user_asp_by_token(self, asp_user_token):
        return SsoUser.objects.filter(user=self.user, asp_user_token=asp_user_token).first()

    #############################################################
    def get_app_users(app):
        return SsoUser.objects.filter(app=app)
    #############################################################