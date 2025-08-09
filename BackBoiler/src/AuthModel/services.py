from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.decorators import login_required
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import app_credential
from drf_spectacular.utils import extend_schema
from UserModel.models import User
from .models import UserAuth
from .serializers import UserAuthSerializer
from RateLimitModel.models import api_user_auth_rate_limit

@extend_schema(
    description='' + "<br><br> <b> App Credential </b>",
    summary='Check user auth token, auth user hash shows session is valid or not. if session is invalid or expired then auth user hash was removed',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'user_token': {'type': 'string', 'default': ''},
            },
            'required': ['user_token'],
        }
    },
    responses={
        200: {'return': True },
    },
)
@api_view(['POST'])
@api_user_auth_rate_limit
@app_credential
def CheckUserAuth(request):
    try:
        user_token = request.data.get('user_token')
        if not user_token:
            return JsonResponse({'error': 'User token is missing.', 'return': False})
        
        ua = UserAuth.objects.get(token=user_token)
        
        return JsonResponse(UserAuthSerializer(ua).data)
    
    except Exception as e:
        return JsonResponse({'error': str(e),'return': False})    
    
