from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import  AllowAny
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import OpenApiResponse
from .models import User
from .serializers import UserSerializer
from AuthModel.models import app_credential
from RateLimitModel.models import user_uuid_limit, api_user_auth_rate_limit
from app.app_lib import get_phonenumber_start_with_zero, CheckPhonenumberValidty, CheckEmailValidty
from AuthModel.models import user_credential , admin_credential


from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

import requests


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
###################################################################
@extend_schema(
    description='Register new user account',
    summary='Create new user with email or phone number' + "<br><br> <b> app Credential </b>",
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'email': {'type': 'string', 'format': 'email'},
                'phone_number': {'type': 'string', 'default':'' , 'description': 'Phone number can be in format 09123211212, +9834567890 or 9834567890'},
                'password': {'type': 'string', 'default': '', 'description': 'Password can be at any size'},
                'first_name': {'type': 'string', 'default': '', 'description': 'First name of user'},
                'last_name': {'type': 'string', 'default': '', 'description': 'Last name of user'},
            },
            'required': ['password']
        }
    },
    responses={
            200: OpenApiResponse(
                response={'return': 'boolean', 'user': 'dict', 'user_token': 'str'},
                description='Successful creation',
            ),
        },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def RegisterUser(request):
    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    
    if not email and not phone_number:
        return JsonResponse({'return': False, 'error': 'Email or phone number required'})
    
    try:
        # Validate email/phone
        if email and not CheckEmailValidty(email):
            return JsonResponse({'return': False, 'error': 'Invalid email format'})
        
        if phone_number and not CheckPhonenumberValidty(phone_number):
            return JsonResponse({'return': False, 'error': f'Invalid phone number {phone_number}'})
        
        # Check if user exists
        if email and User.objects.filter(email=email).exists():
            return JsonResponse({'return': False, 'error': 'Email already registered'})
        
        cleaned_phone = get_phonenumber_start_with_zero(phone_number) if phone_number else None

        if cleaned_phone and User.objects.filter(phone_number=cleaned_phone).exists():
            return JsonResponse({'return': False, 'error': f'Phone number {cleaned_phone} already registered'})
        
        # Create user
        user = User.objects.create_user(
            email=email,
            phone_number=cleaned_phone,
            password=request.data.get('password'),
            first_name=request.data.get('first_name', ''),
            last_name=request.data.get('last_name', ''),
            username= email if email else cleaned_phone
        )
        
        return JsonResponse({
            'return': True, 
            'user': UserSerializer(user).data,
            'user_token': user.auth().token
        })
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
####################################################################
@extend_schema(
    description='User login with email or phone number',
    summary='Authenticate user and get access token',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'email': {'type': 'string', 'format': 'email', 'description': 'User email address'},
                'phone_number': {'type': 'string', 'default': '', 'description': 'Phone number can be in format 09123211212, +9834567890 or 9834567890'},
                'password': {'type': 'string', 'default': '', 'description': 'User password'},
            },
            'required': ['password']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'user': 'dict', 'user_token': 'str'},
            description='Successful login',
        ),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def LoginUser(request):
    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    password = request.data.get('password')
    
    if not email and not phone_number:
        return JsonResponse({'return': False, 'error': 'Email or phone number required'})
    
    if not password:
        return JsonResponse({'return': False, 'error': 'Password required'})
    
    try:
        user = None
        
        # Find user by email or phone
        if email:
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
        
        # Check password directly since we have the user object
        if not user.check_password(password):
            return JsonResponse({'return': False, 'error': 'Invalid credentials'})
        
        # Check if user is active
        if not user.is_active:
            return JsonResponse({'return': False, 'error': 'Account is disabled'})
        
        # Login user using Django's login
        login(request, user)
        
        return JsonResponse({
            'return': True,
            'user': UserSerializer(user).data,
            'user_token': user.auth().token if hasattr(user, 'auth') else None
        })
        
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
    
    
@extend_schema(
    description='User logout',
    summary='Logout user from Django session' + "<br><br> <b> User Authentication Required </b>",
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {},
            'required': []
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'message': 'str'},
            description='Successful logout',
        ),
    },
)
@api_view(['POST'])
@user_credential
def LogoutUser(request):
    try:
        # Logout user using Django's logout
        logout(request)
        
        return JsonResponse({
            'return': True,
            'message': 'Successfully logged out'
        })
        
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})


@extend_schema(
    description='Check if user is authenticated',
    summary='Verify current authentication status' + "<br><br> <b> No Authentication Required </b>",
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'authenticated': 'boolean', 'user': 'dict'},
            description='Authentication status',
        ),
    },
)
@api_view(['GET'])
@permission_classes([AllowAny])
def CheckAuthStatus(request):
    try:
        if request.user.is_authenticated:
            return JsonResponse({
                'return': True,
                'authenticated': True,
                'user': UserSerializer(request.user).data
            })
        else:
            return JsonResponse({
                'return': True,
                'authenticated': False,
                'user': None
            })
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})


@extend_schema(
    description='Change user password',
    summary='Update password for authenticated user' + "<br><br> <b> User Authentication Required </b>",
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'old_password': {'type': 'string', 'description': 'Current password'},
                'new_password': {'type': 'string', 'description': 'New password'},
                'confirm_password': {'type': 'string', 'description': 'Confirm new password'},
            },
            'required': ['old_password', 'new_password', 'confirm_password']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'message': 'str'},
            description='Password changed successfully',
        ),
    },
)
@api_view(['POST'])
@user_credential
def ChangePassword(request):
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')
    
    if not all([old_password, new_password, confirm_password]):
        return JsonResponse({'return': False, 'error': 'All password fields are required'})
    
    if new_password != confirm_password:
        return JsonResponse({'return': False, 'error': 'New passwords do not match'})
    
    try:
        user = request.user
        
        # Check old password
        if not user.check_password(old_password):
            return JsonResponse({'return': False, 'error': 'Current password is incorrect'})
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        return JsonResponse({
            'return': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})


    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    password = request.data.get('password')
    
    if not email and not phone_number:
        return JsonResponse({'return': False, 'error': 'Email or phone number required'})
    
    if not password:
        return JsonResponse({'return': False, 'error': 'Password required'})
    
    try:
        user = None
        username = None
        
        # Find user by email or phone
        if email:
            if not CheckEmailValidty(email):
                return JsonResponse({'return': False, 'error': 'Invalid email format'})
            user_obj = User.objects.filter(email=email).first()
            if user_obj:
                username = user_obj.username
            
        elif phone_number:
            if not CheckPhonenumberValidty(phone_number):
                return JsonResponse({'return': False, 'error': f'Invalid phone number {phone_number}'})
            cleaned_phone = get_phonenumber_start_with_zero(phone_number)
            user_obj = User.objects.filter(phone_number=cleaned_phone).first()
            if user_obj:
                username = user_obj.username
        
        if not username:
            return JsonResponse({'return': False, 'error': 'User not found'})
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            return JsonResponse({'return': False, 'error': 'Invalid credentials'})
        
        if not user.is_active:
            return JsonResponse({'return': False, 'error': 'Account is disabled'})
        
        # Login user
        login(request, user)
        
        # Get session key for API clients
        session_key = request.session.session_key
        
        return JsonResponse({
            'return': True,
            'user': UserSerializer(user).data,
            'user_token': user.auth().token,
            'session_key': session_key  # Can be used for subsequent API calls
        })
        
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})
    
    
User = get_user_model()

@login_required
def get_all_user_ids(request):
    users = User.objects.filter(
        is_active=True
    ).exclude(
        id=request.user.id  
    )
    
    user_data = []
    for user in users:
        telegram_id = user.get_or_fetch_telegram_id()
        user_data.append({
            'id': user.id,
            'telegram_id': telegram_id,
            'phone_number': user.phone_number
        })
    
    return JsonResponse({'users': user_data})


@extend_schema(
    description='Get or fetch telegram_id for a user by id',
    summary='Resolve user telegram_id and persist it',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'user_id': {'type': 'integer'},
            },
            'required': ['user_id']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'telegram_id': 'str|null'},
            description='Resolved telegram id'
        ),
    },
)
@api_view(['POST'])
@login_required
def GetUserTelegramId(request):
    try:
        user_id = request.data.get('user_id') or request.POST.get('user_id')
        if not user_id:
            return JsonResponse({'return': False, 'error': 'user_id is required'})

        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            return JsonResponse({'return': False, 'error': 'User not found'})

        telegram_id = user.get_or_fetch_telegram_id()

        # Persist to model explicitly (in case it was returned but not saved)
        if telegram_id and user.telegram_id != str(telegram_id):
            user.telegram_id = str(telegram_id)
            user.save(update_fields=['telegram_id'])

        # Response aligned with your data expectations (focus on telegram_id)
        return JsonResponse({
            'return': True,
            'telegram_id': telegram_id
        })
    except Exception as e:
        return JsonResponse({'return': False, 'error': str(e)})

@extend_schema(
    description='Get Telegram profile by user phone number',
    summary='Fetch Telegram info (telegram_id/chat_id) for a given phone number',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'phone_number': {'type': 'string', 'description': 'Phone number like 98912... without +'},
            },
            'required': ['phone_number']
        }
    },
    responses={
        200: OpenApiResponse(
            response={'return': 'boolean', 'user': 'object'},
            description='Telegram info'
        ),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def GetTelegramInfo(request):
    phone_number = request.data.get('phone_number')
    if not phone_number:
        return JsonResponse({'return': False, 'error': 'phone_number is required'})

    # Normalize phone to expected format (no leading +, start with country code)
    try:
        cleaned_phone = get_phonenumber_start_with_zero(phone_number)
        # The external service expects without leading 0, using country code
        # If cleaned_phone starts with 0, replace with 98 (Iran) as common pattern
        if cleaned_phone.startswith('0'):
            cleaned_phone = '98' + cleaned_phone[1:]
    except Exception:
        cleaned_phone = phone_number

    # Resolve base URL from config if available
    base_url = None
    try:
        from app.config_utils import config_manager
        if config_manager:
            base_url = config_manager.get('connect.telegram_message_server', None)
    except Exception:
        base_url = None

    if not base_url:
        base_url = 'https://message.imoonex.ir/'  

    url = f"{base_url}/Telegram/GetTelegramUserByMessageDevice/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": '8ca38f71865d141cac8a70fab652e9ac'
    }
    payload = {
        'app_id': 'aimoonhub',
        'message_device': 'sms',
        'to_user_id': cleaned_phone
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=8)
        
    except Exception:
        return JsonResponse({'return': False, 'error': 'Could not connect to message service'})

    if resp.status_code == 200:
        try:
            data = resp.json()
        except Exception:
            return JsonResponse({'return': False, 'error': 'Invalid response from message service'})

        if isinstance(data, dict) and data.get('return') is True:
            return JsonResponse({'return': True, 'user': data.get('user')})
        return JsonResponse({'return': False, 'error': 'Telegram id of user not found' })

    return JsonResponse({'return': False, 'error': 'Telegram id of user not found'})
