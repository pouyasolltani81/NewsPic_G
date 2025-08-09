from django.contrib import admin
from .models import AppServiceProvider, SsoUser

class AppServiceProviderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'app_uuid', 'app_token', 'credential_type', 'route_config', 'is_active', 'create_at')
    search_fields = ('name', 'app_uuid')
    readonly_fields = ('create_at', 'credential_type')

class SsoUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'asp', 'asp_user_uuid', 'asp_user_token', 'is_active', 'last_access_at')
    search_fields = ('user__username', 'asp__name', 'asp_user_uuid')
    readonly_fields = ('create_at', 'last_access_at')

admin.site.register(AppServiceProvider, AppServiceProviderAdmin)
admin.site.register(SsoUser, SsoUserAdmin)