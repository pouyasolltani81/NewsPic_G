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
def GetLogs(request):
    timestamp = request.data.get('timestamp', None)
    try:
        if timestamp:
            aware_timestamp = timezone.make_aware(timezone.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S"))
            logs = Log.objects.using(Log.objects.db_name).filter(timestamp__gte=aware_timestamp)
        else:
            logs = Log.objects.using(Log.objects.db_name).filter(timestamp__gte=timezone.now() - timezone.timedelta(days=1))
        
        return JsonResponse({'return': True,'logs': LogSerializer(logs, many=True).data})
    except Exception as e:
        print_log(request.user, 'error', str(e))
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
        print_log(request.user, 'error', str(e))
        return JsonResponse({'return': False, 'error': str(e)})