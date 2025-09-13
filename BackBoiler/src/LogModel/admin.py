from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Log


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'colored_level', 'user', 'truncated_message', 'exception_type', 'view_name', 'file_location')
    list_filter = ('level', 'timestamp', 'exception_type', 'view_name')
    search_fields = ('message', 'exception_type', 'file_path', 'view_name', 'user__username')
    readonly_fields = ('timestamp', 'user', 'level', 'message', 'exception_type', 'formatted_stack_trace', 'file_path', 'line_number', 'view_name')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('timestamp', 'user', 'level', 'view_name')
        }),
        ('Error Details', {
            'fields': ('message', 'exception_type'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('file_path', 'line_number'),
            'classes': ('collapse',)
        }),
        ('Stack Trace', {
            'fields': ('formatted_stack_trace',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.using('Logs')
    
    def colored_level(self, obj):
        colors = {
            'error': '#dc3545',
            'warning': '#ffc107', 
            'urgent error': '#dc3545',
            'return': '#28a745',
            'info': '#17a2b8'
        }
        color = colors.get(obj.level, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.level.upper()
        )
    colored_level.short_description = 'Level'
    colored_level.admin_order_field = 'level'

    def truncated_message(self, obj):
        if len(obj.message) > 50:
            return f"{obj.message[:50]}..."
        return obj.message
    truncated_message.short_description = 'Message'
    truncated_message.admin_order_field = 'message'

    def file_location(self, obj):
        if obj.file_path and obj.line_number:
            return f"{obj.file_path}:{obj.line_number}"
        return obj.file_path or "-"
    file_location.short_description = 'File:Line'

    def formatted_stack_trace(self, obj):
        if obj.stack_trace:
            return format_html('<pre style="white-space: pre-wrap; font-family: monospace;">{}</pre>', obj.stack_trace)
        return "No stack trace available"
    formatted_stack_trace.short_description = 'Stack Trace'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    actions = ['delete_selected']

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser and 'delete_selected' in actions:
            del actions['delete_selected']
        return actions