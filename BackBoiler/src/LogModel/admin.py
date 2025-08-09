from django.contrib import admin
from .models import Log


class LogAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp', 'level', 'user', 'message', 'exception_type', 'file_path', 'line_number', 'view_name')
    search_fields = ('message', 'exception_type', 'file_path', 'view_name')
    readonly_fields = ('timestamp', 'user', 'level', 'message', 'exception_type', 'stack_trace', 'file_path', 'line_number', 'view_name')

    database = 'Logs'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.using('Logs')
    
admin.site.register(Log,LogAdmin)