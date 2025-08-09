from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import  AllowAny
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import OpenApiResponse
from .models import User
from .serializers import UserSerializer
from AuthModel.models import app_credential
from RateLimitModel.models import user_uuid_limit, api_user_auth_rate_limit

@extend_schema(
    description='With email and password get auth token to use services' + "<br><br> <b> App Credential </b>",
    summary='user to use services should login or has a auth token in request header',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'email': {'type':'string', 'default': ''},
                'password': {'type':'string', 'default': ''},
            },
           'required': ['username','password']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean'},
            description='',
        ),
    },
)
@api_view(['POST'])
@api_user_auth_rate_limit
@app_credential
def GetUserToken(request):
    email = request.data.get('email')
    password = request.data.get('password')
    try:
        user, res = User.get_user_auth(email=email, password=password)
        if user:
            return JsonResponse({'return':True, 'message':'User valid to use services', 'user': UserSerializer(user).data, 'user_token':user.auth().token})
        else:
            return JsonResponse({'return':False, 'message':'User auth invalid: ' + res['error']})
    except Exception as e:
        return JsonResponse({'return':False, 'error':str(e)})
#################################################################
@extend_schema(
    description='Get user details by uuid' + "<br><br> <b> App Credential </b>",
    summary='Get user details by uuid',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'uuid': {'type':'string', 'default': '', 'format': 'uuid', 'description': 'User uuid'},
            },
           'required': ['uuid']
        }
    },

    responses={
        200: OpenApiResponse(
            response={'return': 'boolean'},
            description='',
        ),
    },
)
@api_view(['POST'])
@user_uuid_limit
@app_credential
def GetUserbyUUID(request):
    
    uuid = request.data.get('uuid','')
    
    if not uuid:
        uuid = request.user.uuid
    
    try:
        user = User.objects.get(uuid=uuid)
        return JsonResponse({'return':True, 'user': UserSerializer(user).data})
    except Exception as e:
        return JsonResponse({'return':False, 'error':str(e)})