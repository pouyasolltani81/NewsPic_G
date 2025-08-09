from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.http import JsonResponse
from django.utils import timezone
from AuthModel.models import app_credential, user_credential

from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, OpenApiResponse
from UserModel.models import User
from .models import AppServiceProvider, SsoUser, default_route_config, CREDENTIAL_TYPES
from .serializers import AppServiceProviderSerializer, SsoUserSerializer
from AuthModel.models import UserAuth
from .connects import asp_request_to_exec
from LogModel.log_handler import print_log
from RateLimitModel.models import api_rate_limit

@extend_schema(
    description='Create App Service Provider interface connection with route' +
                '<br><br> <b>Admin Credential</b>',
    summary='Create new service provider in SSO system',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'app_uuid': {'type': 'string', 'format': 'uuid', 'description': 'uuid of the ASP, get it from remote ASP GetConnections API'},
                'name': {'type': 'string', 'default': ''},
                'desc': {'type': 'string', 'default': ''},
                'app_token': {'type': 'string', 'default': ''},
                'route_config': {'type': 'dict', 'default': default_route_config()},
            },
            'required': ['app_uuid', 'name', 'app_token']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'asp': 'dict'},
            description='Successful creation',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@permission_classes((IsAdminUser,))
def CreateASP(request):
    app_uuid = request.data.get('app_uuid')
    name = request.data.get('name')
    desc = request.data.get('desc')
    app_token = request.data.get('app_token')
    route_config = request.data.get('route_config')

    try:    
        asp = AppServiceProvider.create_asp(app_uuid, name, desc, app_token, route_config, credential_type='app')
        asp_serializer = AppServiceProviderSerializer(asp)
        return JsonResponse({'return': True,  'message': 'App Service Provider created successfully.',
                             'asp': asp_serializer.data})
    
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
###############################################################################################
@extend_schema(
    description='Change App Service Provider Status' + '<br><br> <b>Admin Credential</b>',
    summary='Toggle active status of service provider',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'asp_uuid': {'type': 'string', 'format': 'uuid'},
            },
            'required': ['asp_uuid']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'provider': 'dict'},
            description='Status changed successfully',
        ),
    },
)
@api_view(['POST'])
@permission_classes((IsAdminUser,))
def ChangeASPActivation(request):
    app_uuid = request.data.get('asp_uuid')
    try:
        asp = AppServiceProvider.objects.get(app_uuid=app_uuid)
        asp.change_activate()
        
        serializer = AppServiceProviderSerializer(asp)
        return JsonResponse({'return': True, 'message': 'App Service Provider status changed successfully',
            'asp': serializer.data})
    except  Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
###############################################################################################
## SSo User
###############################################################################################
@extend_schema(
    description='Change SSO User Activation Status' + '<br><br> <b>Admin Credential</b>',
    summary='Toggle SSO user active status',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'user_id': {'type': 'string', 'default': '', 'description': 'User ID to get ASPs, if not provided, current user will be used'},
                'asp_uuid': {'type': 'string', 'format': 'uuid'},
            },
            'required': ['asp_uuid']
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean',
                'message': 'string', 
                'sso_user': 'dict'
            },
            description='Status changed successfully',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@permission_classes((IsAdminUser,))
def ChangeUserActivation(request):
    user_id = request.data.get('user_id')
    asp_uuid = request.data.get('asp_uuid')
    
    if user_id == '':
        user_id = request.user.id
    
    try:
        sso_user = SsoUser.objects.get(user__id=user_id, asp__app_uuid=asp_uuid)
        sso_user.change_activate()
        
        serializer = SsoUserSerializer(sso_user)
        return JsonResponse({
            'return': True,
            'message': f"SSO user access {'activated' if sso_user.is_active else 'deactivated'} successfully",
            'sso_user': serializer.data
        })
    except SsoUser.DoesNotExist:
        return JsonResponse({'return': False, 'error': 'SSO user not found'}, status=404)
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
###############################################################################################
@extend_schema(
    description='Get current User ASPs' + '<br><br> <b>User Credential</b>' + '<br><b>Note:</b> this API only works for service logined users',
    summary='Get current user ASPs information',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'user_id': {'type': 'string', 'default': '', 'description': 'User ID to get ASPs, if not provided, current user will be used'},
            },
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean',
                'asps': 'dict'
            },
            description='ASP user details retrieved successfully',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@user_credential
def GetUserAsps(request):

    user_id = request.data.get('user_id')

    try:
        if user_id == '':
            user_id = request.user.id
            
        user = User.objects.get(id=user_id)
        SsoUsers = SsoUser.objects.filter(user__id = user.id)
        
        if SsoUsers.count() > 0:
            return JsonResponse({
                'return': True, 
                'message': 'ASP user details retrieved successfully.',
                'Asps': SsoUserSerializer(SsoUsers, many=True).data
            })
        else:
            return JsonResponse({
                'return': False, 
                'error': 'No ASPs found'
            }, status=404)
            
    except SsoUser.DoesNotExist:
        return JsonResponse({'return': False, 'error': 'Sso user not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
###############################################################################################

@extend_schema(
    description='Get ASP Credential details, it invokes the ASP GetCredential for [app, user, admin] types with details. app for ASP and user and admin for sso users related to destination connect' +
    '<br><br> <b>User Credential</b>',
    summary='Get ASP credential details',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'asp_uuid': {'type': 'string', 'format':'uuid', 'description': 'ASP UUID to get credential'},
                'credential_type': {'type': 'string', 'enum':[choice[0] for choice in CREDENTIAL_TYPES], 'default': 'user', 'description': 'credential type'},
                'asp_user_uuid': {'type': 'string', 'default': '', 'description': 'ASP user UUID to get credential if needed.'},
            },
            'required': ['asp_uuid']
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean',
                'credential': 'dict'
            },
            description='ASP credential details retrieved successfully',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@user_credential
def GetAspCredential(request):
    asp_uuid = request.data.get('asp_uuid')
    credential_type = request.data.get('credential_type')
    asp_user_uuid = request.data.get('asp_user_uuid', '')
    
    try:
        asp = AppServiceProvider.objects.get(app_uuid=asp_uuid, is_active=True)
        
        uuid = asp_user_uuid if asp_user_uuid != '' else asp_uuid
        
        rq_to_exec_params = {
            'asp_uuid': str(asp.app_uuid),
            'route': '/Connect/GetCredential/',
            'method': 'POST',
            'params': {
                'type': credential_type,
                'uuid': str(uuid)
            },
            'headers': {
                'Authorization': asp.app_token,
                'Content-Type': 'application/json'
            }
        }
        
        rq_to_exec_headers = {
            'Authorization': asp.app_token,
            'Content-Type': 'application/json'
        }
        
        con = asp_request_to_exec(asp, rq_to_exec_params, rq_to_exec_headers)
        
        
        return JsonResponse({
            'return': True,
            'message': 'ASP credential details retrieved successfully',
            'asp': AppServiceProviderSerializer(asp).data,
            'connect': con['response']
        })
            
    except AppServiceProvider.DoesNotExist:
        return JsonResponse({'return': False, 'error': 'ASP not found'}, status=404)
    except Exception as e:
        print_log(level='error', message=f'Error: {str(e)}', exception_type=e.__class__.__name__, file_path=__file__, line_number=0, view_name='GetAspCredential')
        return JsonResponse({'return': False, 'error': str(e)})
###############################################################################################
@extend_schema(
    description='Which ASP user i am connected' + '<br><br> <b>User Credential</b>',
    summary='Which ASP user i am connected',
    methods=['POST'],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'asp_uuid': {'type': 'string', 'format':'uuid', 'description': 'ASP UUID to get credential'},
                'user_id': {'type': 'string', 'default': '', 'description': 'User ID to get connected ASPs, if not provided, current user will be used'},
            },
            'required': ['asp_uuid']
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean',
                'credential': 'dict'
            },
            description='ASP credential details retrieved successfully',
        ),
    },
)
@api_view(['POST'])
@api_rate_limit
@user_credential
def GetASPUserbyUserId(request):
    asp_uuid = request.data.get('asp_uuid')
    user_id = request.data.get('user_id')
    
    if user_id == '':
        user_id = request.user.id
        
    try:
        asp = AppServiceProvider.objects.get(app_uuid=asp_uuid, is_active=True)
        
        sso_user = SsoUser.objects.get(asp=asp, user__id=user_id, is_active=True)
        
        asp_user_uuid = sso_user.asp_user_uuid
        
        rq_to_exec_params = {
            'asp_uuid': str(asp.app_uuid),
            'route': '/User/GetUserbyUUID/',
            'method': 'POST',
            'params': {
                'uuid': str(asp_user_uuid)
            },
            'headers': {
                'Authorization': asp.app_token,
                'Content-Type': 'application/json'
            }
        }
        
        rq_to_exec_headers = {
            'Authorization': asp.app_token,
            'Content-Type': 'application/json'
        }
        
        
        con = asp_request_to_exec(asp, rq_to_exec_params, headers=rq_to_exec_headers)
        
        return JsonResponse({
            'return': True,
            'message': 'ASP credential details retrieved successfully',
            'asp': AppServiceProviderSerializer(asp).data,
            'connect': con['response']
        })
            
    except AppServiceProvider.DoesNotExist:
        return JsonResponse({'return': False, 'error': 'ASP not found'}, status=404)
    except SsoUser.DoesNotExist:
        return JsonResponse({'return': False, 'error': 'SSO user not found'}, status=404)
    except Exception as e:
        print_log(level='error', message=f'Error: {str(e)}', exception_type=e.__class__.__name__, file_path=__file__, line_number=0, view_name='GetASPUserbyUserId')
        return JsonResponse({'return': False, 'error': str(e)})