from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.http import JsonResponse
from AuthModel.models import user_credential
from .models import Log
from .log_handler import print_log
from .serializers import LogSerializer
from RateLimitModel.models import api_search_rate_limit, api_rate_limit
import inspect

        
@extend_schema(
    description='Retrieve logs from a given timestamp until now.',
    summary='Get logs within a specific time range',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'timestamp': {'type':'string', 
                              'format':'date-time', 
                              'default': (timezone.now() - timezone.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), 
                              'description':'Start timestamp for log retrieval'},
            },
        }
    },
    responses={
        200: OpenApiResponse(
            response=LogSerializer(many=True),
            description='List of logs from the given timestamp until now',
        ),
    },
)
@api_view(['POST'])
@api_search_rate_limit
@permission_classes((IsAdminUser,))
@extend_schema(
    description='Get system logs with filtering',
    summary='Retrieve logs from specified timestamp',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'timestamp': {'type': 'string', 'format': 'date-time', 'description': 'Filter logs from this timestamp (YYYY-MM-DD HH:MM:SS)'},
                'level': {'type': 'string', 'description': 'Filter by log level'},
                'is_error': {'type': 'boolean', 'description': 'Filter only errors'},
                'api_endpoint': {'type': 'string', 'description': 'Filter by API endpoint'},
                'user_id': {'type': 'integer', 'description': 'Filter by user ID'},
            }
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'logs': 'array'},
            description='Logs retrieved successfully',
        ),
    },
)
def GetLogs(request):
    timestamp = request.data.get('timestamp', None)
    level_filter = request.data.get('level', None)
    is_error_filter = request.data.get('is_error', None)
    api_endpoint_filter = request.data.get('api_endpoint', None)
    user_id_filter = request.data.get('user_id', None)
    
    try:
        # Start with base queryset
        logs = Log.objects.using(Log.objects.db_name).all()
        
        # Apply timestamp filter
        if timestamp:
            aware_timestamp = timezone.make_aware(
                timezone.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            )
            logs = logs.filter(timestamp__gte=aware_timestamp)
        else:
            # Default to last 24 hours
            logs = logs.filter(
                timestamp__gte=timezone.now() - timezone.timedelta(days=1)
            )
        
        # Apply additional filters
        if level_filter:
            logs = logs.filter(level=level_filter)
        
        if is_error_filter is not None:
            logs = logs.filter(is_error=is_error_filter)
        
        if api_endpoint_filter:
            logs = logs.filter(api_endpoint__icontains=api_endpoint_filter)
        
        if user_id_filter:
            logs = logs.filter(user_id=user_id_filter)
        
        # Log this request
        # print_log(
        #     user=request.user,
        #     level='info',
        #     message=f'Logs retrieved by {request.user.username}',
        #     view_name='GetLogs',
        #     file_path=__file__,
        #     line_number=inspect.currentframe().f_lineno,
        #     request=request
        # )
        
        return JsonResponse({
            'return': True,
            'logs': LogSerializer(logs, many=True).data,
            'count': logs.count()
        })
        
    except Exception as e:
        print_log(
            user=request.user,
            level='error',
            message=str(e),
            exception_type=type(e).__name__,
            view_name='GetLogs',
            file_path=__file__,
            line_number=inspect.currentframe().f_lineno,
            request=request,
            error_category='server'
        )
        return JsonResponse({'return': False, 'error': str(e)})
############################################################################################
@extend_schema(
    description='Delete All Logs',
    summary='Delete logs ',
    methods=['GET'],
    
    responses={
        200: OpenApiResponse(
            description='Empty Logs Database',
        ),
    },
)
@api_view(['GET'])
@api_rate_limit
@permission_classes((IsAdminUser,))
def DeleteAllLogs(request):
    
    try:
        Log.objects.using(Log.objects.db_name).all().delete()

        return JsonResponse({'return': True, 'message': 'All logs deleted successfully.'})
    except Exception as e:
        print_log(request.user, 'error', str(e), exception_type='DeleteAllLogsError', view_name='DeleteAllLogs', file_path=__file__, line_number=__import__('inspect').currentframe().f_lineno)
        return JsonResponse({'return': False, 'error': str(e)})