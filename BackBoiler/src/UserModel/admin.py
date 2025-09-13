from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('id','is_active', 'uuid', 'username', 'email', 'phone_number', 'status_badge', 'online_indicator', 'last_activity_at','date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'phone_number', 'uuid')
    ordering = ('-date_joined',)
    list_per_page = 50
    date_hierarchy = 'date_joined'
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number')}),
        ('Status', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Activity', {'fields': ('last_activity_at', ), 'classes': ('collapse',)}),
        ('Important dates', {'fields': ('last_login', 'date_joined'), 'classes': ('collapse',)}),
        ('System', {'fields': ('uuid',), 'classes': ('collapse',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email', 'phone_number', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('uuid', 'last_activity_at', 'date_joined', 'last_login')
    filter_horizontal = ()  # Removes groups and permissions widgets
    
    def status_badge(self, obj):
        if obj.is_superuser:
            return format_html('<span style="color: #ff6b6b;">●</span> Superuser')
        elif obj.is_staff and obj.is_active:
            return format_html('<span style="color: #4ecdc4;">●</span> Staff')
    status_badge.short_description = 'Role'
    
    def online_indicator(self, obj):
        if obj.is_online:
            return format_html('<span style="color: #00b894;">● Online</span>')
        return format_html('<span style="color: #b2bec3;">○ Offline</span>')
    online_indicator.short_description = 'Online'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(is_superuser=False)
        return qs
    
    actions = ['activate_users', 'deactivate_users']
    
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f'{updated} users deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'