import sys
from rest_framework.views import exception_handler
from django.utils.deprecation import MiddlewareMixin
from django.http import Http404
from django.core.exceptions import PermissionDenied
import traceback
from .models import Log

def print_log(user=None, level='error', message='', exception_type='', stack_trace='', file_path='', line_number=0, view_name=''):
    Log.objects.using(Log.objects.db_name).create(
        user=user,
        level=level,
        message=f'print_log: {message}',
        exception_type=exception_type,
        stack_trace=stack_trace,
        file_path=file_path,
        line_number=line_number,
        view_name=view_name
    )

class drf_ExceptionMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        Log.objects.using(Log.objects.db_name).create(
            level='error',
            message=f'drf_ExceptionMiddleware.process_exception: {str(exception)}',
            exception_type=exception.__class__.__name__,
            stack_trace=traceback.format_exc(),
            file_path=traceback.extract_tb(exception.__traceback__)[-1].filename,
            line_number=traceback.extract_tb(exception.__traceback__)[-1].lineno,
            view_name=request.resolver_match.view_name if request.resolver_match else None,
            user=request.user if request.user.is_authenticated else None
        )
        return None
    
def request_processing_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        level = 'error'
        if isinstance(exc, Http404):
            level = 'warning'
        elif isinstance(exc, PermissionDenied):
            level = 'urgent error'

        Log.objects.using(Log.objects.db_name).create(
            level=level,
            message=f'request_processing_exception_handler: {str(exc)}',
            exception_type=exc.__class__.__name__,
            stack_trace=traceback.format_exc(),
            file_path=traceback.extract_tb(exc.__traceback__)[-1].filename,
            line_number=traceback.extract_tb(exc.__traceback__)[-1].lineno,
            view_name=context['view'].__class__.__name__ if 'view' in context else None,
            user=context['request'].user if 'request' in context and context['request'].user.is_authenticated else None
        )

    return response

def hook_exception_handler(exc_type, exc_value, exc_traceback):
    Log.objects.using(Log.objects.db_name).create(
        level='error',
        message=f'hook_exception_handler: {str(exc_value)}',
        exception_type=exc_type.__name__,
        stack_trace=''.join(traceback.format_tb(exc_traceback)),
        file_path=traceback.extract_tb(exc_traceback)[-1].filename,
        line_number=traceback.extract_tb(exc_traceback)[-1].lineno,
    )
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = hook_exception_handler
