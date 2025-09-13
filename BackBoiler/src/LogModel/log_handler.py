import sys
import traceback
from typing import Optional, Union, Dict, Any
from contextlib import contextmanager

from rest_framework.views import exception_handler
from django.utils.deprecation import MiddlewareMixin
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.contrib.auth.models import AnonymousUser

from .models import Log, LEVEL_CHOICES



import os
import inspect
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.contrib.auth.models import User



class LogHandler:
    """Centralized log handling with error safety and cross-database support."""
    
    VALID_LEVELS = [choice[0] for choice in LEVEL_CHOICES]
    
    @classmethod
    def _extract_traceback_info(cls, tb: Optional[object]) -> tuple[str, int]:
        """Extract file path and line number from traceback."""
        if not tb:
            return '', 0
        
        try:
            extracted = traceback.extract_tb(tb)
            if extracted:
                last_frame = extracted[-1]
                return last_frame.filename, last_frame.lineno
        except Exception:
            pass
        
        return '', 0
    
    @classmethod
    def _get_user_id_safely(cls, user: Any) -> Optional[int]:
        """Safely get user ID, handling AnonymousUser and cross-database issues."""
        if not user or isinstance(user, AnonymousUser):
            return None
        
        if hasattr(user, 'is_authenticated') and user.is_authenticated:
            try:
                return user.pk if user.pk else None
            except Exception:
                return None
        return None
    
    @classmethod
    def _get_username_safely(cls, user: Any) -> str:
        """Safely get username for logging purposes."""
        if not user or isinstance(user, AnonymousUser):
            return 'Anonymous'
        
        try:
            if hasattr(user, 'username'):
                return user.username
            elif hasattr(user, 'email'):
                return user.email
            else:
                return f'User_{user.pk}' if hasattr(user, 'pk') else 'Unknown'
        except Exception:
            return 'Unknown'
    
    @classmethod
    def _validate_level(cls, level: str) -> str:
        """Validate and return log level."""
        return level if level in cls.VALID_LEVELS else 'error'
    
    @classmethod
    @contextmanager
    def _safe_log_creation(cls):
        """Context manager for safe log creation with error handling."""
        try:
            yield
        except (DatabaseError, Exception) as e:
            # Fallback to console logging if database fails
            print(f"Failed to create log entry: {e}", file=sys.stderr)
    
    @classmethod
    def create_log(cls, 
                  user: Optional[object] = None,
                  level: str = 'error',
                  message: str = '',
                  exception_type: str = '',
                  stack_trace: str = '',
                  file_path: str = '',
                  line_number: int = 0,
                  view_name: Optional[str] = None,
                  prefix: str = '') -> bool:
        """Create a log entry with validation and error handling."""
        
        # Handle user information safely for cross-database compatibility
        user_id = cls._get_user_id_safely(user)
        username = cls._get_username_safely(user)
        
        # Include username in message if user exists
        final_message = f'{prefix}: {message}' if prefix else message
        if username != 'Anonymous':
            final_message = f'[{username}] {final_message}'
        
        with cls._safe_log_creation():
            # Create log without user foreign key to avoid cross-database issues
            log_data = {
                'level': cls._validate_level(level),
                'message': final_message,
                'exception_type': exception_type,
                'stack_trace': stack_trace,
                'file_path': file_path,
                'line_number': line_number,
                'view_name': view_name,
            }
            
            # Only add user if we have a valid user_id and it's safe
            if user_id:
                try:
                    # Test if we can safely reference the user
                    log_data['user_id'] = user_id
                    Log.objects.using(Log.objects.db_name).create(**log_data)
                except Exception:
                    # If foreign key fails, create without user reference
                    log_data.pop('user_id', None)
                    Log.objects.using(Log.objects.db_name).create(**log_data)
            else:
                Log.objects.using(Log.objects.db_name).create(**log_data)
            
            return True
        return False



def print_log(user, level, message, exception_type='', view_name='', file_path='', line_number=0, request=None, error_category='none'):
    """
    Enhanced logging function with more detailed information
    """
    try:
        # Get the full file path
        full_file_path = os.path.abspath(file_path) if file_path else ''
        
        # Extract just the filename for the file_path field
        filename = os.path.basename(file_path) if file_path else ''
        
        # Determine if it's an error
        is_error = level.lower() in ['error', 'critical', 'urgent error']
        
        # Get request information if available
        api_endpoint = ''
        http_method = ''
        request_path = ''
        user_ip = None
        user_agent = ''
        
        if request:
            # Get the API endpoint
            try:
                resolver_match = resolve(request.path)
                api_endpoint = f"{resolver_match.namespace}:{resolver_match.url_name}" if resolver_match.namespace else resolver_match.url_name
                if not api_endpoint:
                    api_endpoint = resolver_match.view_name
            except Resolver404:
                api_endpoint = request.path
            
            # Get HTTP method
            http_method = request.method
            
            # Get full request path with query string
            request_path = request.get_full_path()
            
            # Get user IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                user_ip = x_forwarded_for.split(',')[0]
            else:
                user_ip = request.META.get('REMOTE_ADDR')
            
            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Get user from request if not provided
            if not user and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
        
        # Auto-categorize error if not provided
        if error_category == 'none' and is_error:
            if 'permission' in message.lower() or 'forbidden' in message.lower():
                error_category = 'permission'
            elif 'auth' in message.lower() or 'login' in message.lower():
                error_category = 'authentication'
            elif 'not found' in message.lower() or '404' in message:
                error_category = 'not_found'
            elif 'database' in message.lower() or 'db' in message.lower():
                error_category = 'database'
            elif 'validation' in message.lower() or 'invalid' in message.lower():
                error_category = 'validation'
            elif 'api' in message.lower() and 'external' in message.lower():
                error_category = 'external_api'
            else:
                error_category = 'unknown'
        
        # Create log entry
        Log.objects.using(Log.objects.db_name).create(
            user=user if user and isinstance(user, User) else None,
            level=level,
            message=message,
            exception_type=exception_type,
            file_path=filename,
            full_file_path=full_file_path,
            line_number=line_number,
            view_name=view_name,
            api_endpoint=api_endpoint,
            http_method=http_method,
            is_error=is_error,
            error_category=error_category,
            request_path=request_path,
            user_ip=user_ip,
            user_agent=user_agent
        )
        
    except Exception as e:
        # Fallback logging to console if database logging fails
        print(f"Failed to log: {e}")
        print(f"Original log: {level} - {message}")

class DRFExceptionMiddleware(MiddlewareMixin):
    """Django middleware to log exceptions in DRF views."""
    
    def process_exception(self, request, exception: Exception) -> None:
        """Process and log exceptions from Django views."""
        
        file_path, line_number = LogHandler._extract_traceback_info(exception.__traceback__)
        view_name = None
        
        if hasattr(request, 'resolver_match') and request.resolver_match:
            view_name = request.resolver_match.view_name
        
        LogHandler.create_log(
            user=getattr(request, 'user', None),
            level='error',
            message=str(exception),
            exception_type=exception.__class__.__name__,
            stack_trace=traceback.format_exc(),
            file_path=file_path,
            line_number=line_number,
            view_name=view_name,
            prefix='DRFExceptionMiddleware.process_exception'
        )
        
        return None


def request_processing_exception_handler(exc: Exception, context: Dict[str, Any]):
    """
    Custom DRF exception handler that logs exceptions.
    
    Args:
        exc: The exception instance
        context: Context dictionary containing request and view info
    
    Returns:
        Response object or None
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Determine log level based on exception type
        level_mapping = {
            Http404: 'warning',
            PermissionDenied: 'urgent error'
        }
        level = level_mapping.get(type(exc), 'error')
        
        file_path, line_number = LogHandler._extract_traceback_info(exc.__traceback__)
        
        # Extract view name safely
        view_name = None
        if 'view' in context and hasattr(context['view'], '__class__'):
            view_name = context['view'].__class__.__name__
        
        # Extract user safely
        user = None
        if 'request' in context and hasattr(context['request'], 'user'):
            user = context['request'].user
        
        LogHandler.create_log(
            user=user,
            level=level,
            message=str(exc),
            exception_type=exc.__class__.__name__,
            stack_trace=traceback.format_exc(),
            file_path=file_path,
            line_number=line_number,
            view_name=view_name,
            prefix='request_processing_exception_handler'
        )

    return response


def global_exception_handler(exc_type: type, exc_value: Exception, exc_traceback: object) -> None:
    """
    Global exception handler for uncaught exceptions.
    
    Args:
        exc_type: Exception type
        exc_value: Exception instance
        exc_traceback: Traceback object
    """
    file_path, line_number = LogHandler._extract_traceback_info(exc_traceback)
    
    LogHandler.create_log(
        level='error',
        message=str(exc_value),
        exception_type=exc_type.__name__,
        stack_trace=''.join(traceback.format_tb(exc_traceback)),
        file_path=file_path,
        line_number=line_number,
        prefix='global_exception_handler'
    )
    
    # Call the original exception handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


# Set global exception handler
sys.excepthook = global_exception_handler