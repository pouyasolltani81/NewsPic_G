from django.contrib import admin
from .models import UserAuth


class UserAuthAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'token', 'created_at', 'expired_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('token', 'created_at')


admin.site.register(UserAuth,UserAuthAdmin)