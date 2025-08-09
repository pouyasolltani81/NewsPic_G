from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from AuthModel.models import app_credential, admin_credential, user_credential
from django.http import JsonResponse
from .models import Connect, CREDENTIAL_TYPES
from UserModel.models import User
from AuthModel.serializers import UserAuthSerializer
from .serializers import ConnectSerializer
from app import settings
import json
from LogModel.log_handler import print_log
from RateLimitModel.models import api_rate_limit, api_search_rate_limit

@extend_schema(
    description='Create new app connection interface (to be used by other apps) with name and token' + "<br><br> <b>Admin Credential</b>",
    summary='Create new connection for other service access',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'default': ''},
                'desc': {'type': 'string', 'default': ''},
            },
            'required': ['name']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean'},
            description='Connection created successfully',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@permission_classes([IsAdminUser])
def CreateConnection(request):
    try:
        name=request.data.get('name', settings.APP_NAME)
        desc=request.data.get('desc', '')
        
        connection = Connect.create_connect(name=name, desc=desc, type='app')
        return JsonResponse({ 'return': True, 'message': 'Connection created successfully', 'connect': ConnectSerializer(connection).data})
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
#################################################################################
@extend_schema(
    description='Get all app active connections' + "<br><br> <b>Admin Credential</b>",
    summary='List all app active connections for service access',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean'},
            description='List of all active connections',
        ),
    },
)
@api_view(['GET'])
@api_search_rate_limit
@admin_credential
def GetConnections(request):
    try:
        connections = Connect().get_active_connects()
        return JsonResponse({
            'return': True,
            'message': 'Active connections retrieved successfully',
            'connections': ConnectSerializer(connections, many=True).data
        })
    except Exception as e:
        return JsonResponse({
            'return': False,
            'error': str(e)
        })
#################################################################################
@extend_schema(
    description='Get or retrun connection credential for uuid of [app, user, admin] type' + 'for app get from connect; for user and admin get from user and user auth' +
    "<br><br> <b> App Credential</b>",
    summary='get connection credentials. for [app, user, admin] types.',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'type': {'type': 'string', 'default':'app', 'enum': [choice[0] for choice in CREDENTIAL_TYPES]},
                'uuid': {'type': 'string', 'format': 'uuid', 'default': '', 'description': 'if type in [app, user, admin] then need app_uuid or user_uuid'},
            },
            'required': ['type', 'uuid']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean'},
            description='Connection processed successfully',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@app_credential
def GetCredential(request):
    try:
        
        type = request.data.get('type')
        uuid = request.data.get('uuid', '')
        
        user_credential = {}
        admin_credential = {}
        app_credential = {}
        
        if type in ['user'] and uuid:
            user = User.objects.filter(uuid=uuid, is_active=True).first()
            if user:
                user_credential = UserAuthSerializer(user.auth()).data 
            else:
                user_credential = {'uuid': uuid, 'error': 'invalid user uuid'}
            
        if type in ['admin'] and uuid:
            user = User.objects.filter(uuid=uuid, is_superuser=True, is_active=True).first()
            if user:
                admin_credential = UserAuthSerializer(user.auth()).data
            else:
                admin_credential = {'uuid': uuid, 'error': 'invalid admin uuid'}
        
        if type in ['app'] and uuid:
            Connects = Connect.get_active_connects()
            connect = Connects.filter(uuid = uuid, type=type).first()
            if connect:
                app_credential = ConnectSerializer(connect).data
            else:
                app_credential = {'uuid': uuid, 'error': 'invalid app uuid'}
            
        return JsonResponse({'return': True, 'message': 'Connection processed successfully.',
                             'user_credential': user_credential,
                             'admin_credential': admin_credential,
                             'app_credential': app_credential})
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
#################################################################################

@extend_schema(
    description='Change connection active status (is_active)' + "<br><br> <b>Admin Credential</b>",
    summary='active or disactive a connection',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'uuid': {'type': 'string', 'format': 'uuid', 'description': 'app UUID of the connection to update'},
                'is_active': {'type': 'boolean', 'default': True, 'description': 'Set to true to enable or false to disable the connection'},
            },
            'required': ['uuid', 'is_active']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean'},
            description='Connection status updated successfully',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@permission_classes([IsAdminUser])
def ChangeConnectionActivation(request):
    try:
        uuid = request.data.get('uuid')
        is_active = request.data.get('is_active')
        
        # Convert string to boolean if needed
        if isinstance(is_active, str):
            is_active = is_active.lower() == 'true'
        
        connection = Connect.objects.filter(uuid=uuid).first()
        if not connection:
            return JsonResponse({'return': False, 'error': 'Connection not found'})
        
        connection.is_active = is_active
        connection.save()
        
        return JsonResponse({
            'return': True, 
            'message': f'Connection {"activated" if is_active else "deactivated"} successfully',
            'connection': ConnectSerializer(connection).data
        })
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
#################################################################################

@extend_schema(
    description='Execute a service route with provided parameters' + 
    '<br> <b> route </b> to execute (e.g., "/api/connect/get-connections/")' +
    '<br> <b> method </b> to execute (e.g., "GET", "POST", "PUT", "DELETE")' +
    '<br> <b> params </b> to pass to the service, i.e: "uuid":"1234" ' +
    '<br> <b> headers </b> to include in the request, i.e: "key":"1234"' + ' Authorization header is required for all requests, look at the route credential then for [app] is app_token and for [admin,user] credential is user_token' +
    '<br><br> <b>Admin Credential</b>',
    summary='Dynamic service execution',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'asp_uuid': {'type': 'string', 'format': 'uuid', 'description': 'UUID of the ASP to execute the service on'},
                'route': {'type': 'string', 'description': 'Service route to execute (e.g., "/api/connect/get-connections/")', 'default': ''},
                'method': {'type': 'string', 'enum': ['GET', 'POST', 'PUT', 'DELETE'], 'default': 'POST'},
                'params': {'type': 'dict', 'description': 'string of parameters to pass to the service, i.e: "uuid":"1234" ', 'default': '{}'},
                'headers': {'type': 'dict', 'description': 'string of headers to include in the request, i.e: "key":"1234"', 'default': '{"Content-Type": "application/json", "Authorization":""}'},
            },
            'required': ['route']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean'},
            description='Service execution result',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@app_credential
def RequestToExec(request):
    try:
        import requests
        
        asp_uuid = request.data.get('asp_uuid', '')
        connect = Connect.objects.filter(uuid=asp_uuid, is_active=True).first()
        if not connect:
            return JsonResponse({'return': False, 'error': 'Invalid ASP UUID or ASP is not active'})
        
        route = request.data.get('route', '')
        method = request.data.get('method', 'POST').upper()
        params_str = request.data.get('params', '{}')
        headers_str = request.data.get('headers', '{}')

        # run route api in local, so needs address of current site
        from django.contrib.sites.shortcuts import get_current_site
        current_site = get_current_site(request)
        is_secure = request.is_secure()
        protocol = 'https' if is_secure else 'http'
        domain = protocol + '://' + current_site.domain
        
        url = f"{domain}{route}"
        
        params = json.loads(params_str) if isinstance(params_str, str) else params_str
        headers = json.loads(headers_str) if isinstance(headers_str, str) else headers_str
        
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=params)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=params)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, json=params)
        else:
            return JsonResponse({'return': False, 'error': 'Invalid HTTP method'})
        
        return JsonResponse({'return': True, 'message': f'Service {url} executed successfully', 'response': response.json()
        })
        
    except Exception as e:
        print_log(level='error', message=f'Error RequestToExec: {str(e)}', exception_type=e.__class__.__name__, file_path=__file__, line_number=0, view_name='RequestToExec')
        return JsonResponse({'return': False, 'error': str(e)})
