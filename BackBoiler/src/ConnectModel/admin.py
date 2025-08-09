from django.contrib import admin
from .models import Connect

class ConnectAdmin(admin.ModelAdmin):
    list_display = ('id', 'uuid', 'type', 'name', 'desc', 'token', 'is_active', 'created_at', 'updated_at')
    search_fields = ('id', 'uuid', 'name')
    readonly_fields = ('id', 'uuid', 'type', 'token', 'created_at', 'updated_at')
    ordering = ('-created_at',)

admin.site.register(Connect, ConnectAdmin)