from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.decorators import login_required
from rest_framework.permissions import IsAuthenticated, AllowAny
from app.app_lib import get_phonenumber_start_with_zero, CheckPhonenumberValidty, CheckEmailValidty
from django.utils import timezone
from datetime import timedelta
from .models import app_credential , admin_credential
from drf_spectacular.utils import extend_schema
from UserModel.models import User
from .models import UserAuth
from .serializers import UserAuthSerializer
from RateLimitModel.models import api_user_auth_rate_limit
from drf_spectacular.utils import OpenApiResponse


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
    

##########################################################################################################################



@extend_schema(
    description='Admin endpoint to extend user authentication token',
    summary='Extend user token by specified duration',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'user_id': {'type': 'integer', 'description': 'User ID whose token needs to be extended'},
                'email': {'type': 'string', 'format': 'email', 'description': 'User email (alternative to user_id)'},
                'phone_number': {'type': 'string', 'description': 'User phone number (alternative to user_id)'},
                'extension_days': {'type': 'integer', 'default': 365, 'description': 'Number of days to extend (default: 365)'},
                'from_now': {'type': 'boolean', 'default': False, 'description': 'If true, extend from current date. If false, extend from current expiry date'},
            },
            'required': []
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean', 
                'message': 'string',
                'user_id': 'integer',
                'token': 'string',
                'old_expiry': 'string',
                'new_expiry': 'string'
            },
            description='Token extension result',
        ),
    },
)
@api_view(['POST'])
@admin_credential  # Using your admin decorator
def ExtendUserToken(request):
    user_id = request.data.get('user_id')
    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    extension_days = request.data.get('extension_days', 365)
    from_now = request.data.get('from_now', False)
    
    # Validate that at least one identifier is provided
    if not user_id and not email and not phone_number:
        return JsonResponse({
            'return': False, 
            'error': 'Please provide user_id, email, or phone_number'
        })
    
    try:
        user = None
        
        # Find user by different identifiers
        if user_id:
            user = User.objects.filter(id=user_id).first()
        elif email:
            if not CheckEmailValidty(email):
                return JsonResponse({'return': False, 'error': 'Invalid email format'})
            user = User.objects.filter(email=email).first()
        elif phone_number:
            if not CheckPhonenumberValidty(phone_number):
                return JsonResponse({'return': False, 'error': f'Invalid phone number {phone_number}'})
            cleaned_phone = get_phonenumber_start_with_zero(phone_number)
            user = User.objects.filter(phone_number=cleaned_phone).first()
        
        if not user:
            return JsonResponse({'return': False, 'error': 'User not found'})
        
        # Get or create UserAuth
        user_auth, created = UserAuth.objects.get_or_create(user=user)
        
        old_expiry = user_auth.expired_at
        
        if from_now:
            # Extend from current date
            user_auth.expired_at = timezone.now() + timedelta(days=extension_days)
        else:
            # Extend from current expiry date
            if user_auth.expired_at < timezone.now():
                # If already expired, extend from now
                user_auth.expired_at = timezone.now() + timedelta(days=extension_days)
            else:
                # Extend from current expiry
                user_auth.expired_at = user_auth.expired_at + timedelta(days=extension_days)
        
        user_auth.save()
        
        return JsonResponse({
            'return': True,
            'message': f'Token extended successfully for user {user.email}',
            'user_id': user.id,
            'token': user_auth.token,
            'old_expiry': old_expiry.isoformat() if old_expiry else None,
            'new_expiry': user_auth.expired_at.isoformat()
        })
        
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})