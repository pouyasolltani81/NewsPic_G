from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiResponse
from UserModel.models import User
from .models import RateLimit, BlackList, WhiteList, RATE_LIMIT_ENDPOINTS
from .serializers import RateLimitSerializer, BlackListSerializer, WhiteListSerializer
from AuthModel.models import app_credential, user_credential
from LogModel.log_handler import print_log
from django.db import models
from .models import RATE_LIMIT_ENDPOINTS, api_rate_limit, api_search_rate_limit

@extend_schema(
    description='Get paginated list of rate limit records' + '<br><br> <b>Admin Credential</b>' +
    '<br><br> <b>Parameters</b>: This endpoint supports ' +
    '<br> pagination parameters (page, page_size), <br> filter parameters (ip_address, user_id, endpoint, window_minutes), and sorting (order_by). ' +
    '<br> <b> window_minutes </b> is an integer that filters records within the last X minutes (0 for all records). ' +
    '<br> <b> ip_address </b> is a string that filters records by IP address.' +
    '<br> <b> user_id </b> is an integer that filters records by user ID.' +
    '<br> <b> endpoint </b> is a string that filters records by endpoint and is one of the following: ' +
    ', '.join([f'{ep}' for ep in RATE_LIMIT_ENDPOINTS.keys()]) +
    '<br> <b> order_by </b> is a string that can be one of the following: ' +
    'window_start, -window_start, request_count, -request_count, created_at, -created_at, updated_at, -updated_at.',
    summary='Get rate limit records with pagination',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'page': {'type': 'integer', 'default': 1, 'description': 'Page number'},
                'page_size': {'type': 'integer', 'default': 20, 'description': 'Number of records per page (max 100)'},
                'ip_address': {'type': 'string', 'default': '', 'description': 'Filter by IP address'},
                'user_id': {'type': 'string', 'default': '', 'description': 'Filter by user ID'},
                'endpoint': {'type': 'string', 'default': '', 'description': 'Filter by endpoint'},
                'window_minutes': {'type': 'integer', 'default': 0, 'description': 'Filter records within last X minutes (0 for all)'},
                'order_by': {'type': 'string', 'default': '-window_start', 'description': 'Order by field (window_start, -window_start, request_count, -request_count)'},
            }
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean', 
                'rate_limits': 'list',
                'pagination': 'dict',
                'filters': 'dict'
            },
            description='Rate limit records retrieved successfully',
        ),
    },
)
@api_view(['POST'])
@permission_classes((IsAdminUser,))
@api_search_rate_limit
def GetRateLimitList(request):
    try:
        # Get pagination parameters
        page = request.data.get('page', 1)
        page_size = min(request.data.get('page_size', 20), 100)  # Max 100 per page
        
        # Get filter parameters
        ip_address = request.data.get('ip_address', '')
        user_id = request.data.get('user_id', '')
        endpoint = request.data.get('endpoint', '')
        window_minutes = request.data.get('window_minutes', 0)
        order_by = request.data.get('order_by', '-window_start')
        
        # Validate order_by field
        valid_order_fields = ['window_start', '-window_start', 'request_count', '-request_count', 
                             'created_at', '-created_at', 'updated_at', '-updated_at']
        if order_by not in valid_order_fields:
            order_by = '-window_start'
        
        # Build query filters
        filters = {}
        
        if ip_address:
            filters['ip_address'] = ip_address
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                filters['user'] = user
            except User.DoesNotExist:
                return JsonResponse({'return': False, 'error': 'User not found'}, status=404)
        
        if endpoint:
            filters['endpoint'] = endpoint
        
        if window_minutes > 0:
            window_start = timezone.now() - timedelta(minutes=window_minutes)
            filters['window_start__gte'] = window_start
        
        # Get queryset with filters
        queryset = RateLimit.objects.filter(**filters).order_by(order_by)
        
        # Calculate pagination
        total_count = queryset.count()
        total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
        
        # Validate page number
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get paginated results
        rate_limits = queryset[offset:offset + page_size]
        
        # Calculate statistics
        total_requests = queryset.aggregate(total=models.Sum('request_count'))['total'] or 0
        
        unique_ips = queryset.values('ip_address').distinct().count()
        unique_users = queryset.filter(user__isnull=False).values('user').distinct().count()
        unique_endpoints = queryset.values('endpoint').distinct().count()
        
        return JsonResponse({
            'return': True,
            'message': 'Rate limit records retrieved successfully',
            'rate_limits': RateLimitSerializer(rate_limits, many=True).data,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1,
                'next_page': page + 1 if page < total_pages else None,
                'previous_page': page - 1 if page > 1 else None,
            },
            'statistics': {
                'total_requests': total_requests,
                'unique_ips': unique_ips,
                'unique_users': unique_users,
                'unique_endpoints': unique_endpoints,
            },
            'filters': {
                'ip_address': ip_address,
                'user_id': user_id,
                'endpoint': endpoint,
                'window_minutes': window_minutes,
                'order_by': order_by,
            }
        })
        
    except Exception as e:
        print_log(level='error', message=f'Error getting rate limit list: {str(e)}', exception_type=e.__class__.__name__, file_path=__file__, 
                 line_number=0, view_name='GetRateLimitList')
        return JsonResponse({'return': False, 'error': str(e)})

###############################################################################################
@extend_schema(
    description='Get paginated list of blacklist records' + '<br><br> <b>Admin Credential</b>'+
    '<br><br> <b>Parameters</b>: This endpoint supports ' +
    '<br> pagination parameters (page, page_size), <br> filter parameters (ip_address, user_id, blacklist_type, reason, is_active, is_permanent, created_by), and sorting (order_by). ' +
    '<br> <b> order_by </b> is a string that can be one of the following: created_at, updated_at, expires_at, violation_count, last_violation.' +
    '<br> <b> blacklist_type </b> can be one of the following: ip, user, both.' +
    '<br> <b> is_permanent </b> is a boolean that filters permanent blacklists.',
    summary='Get blacklist records with pagination',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'page': {'type': 'integer', 'default': 1, 'description': 'Page number'},
                'page_size': {'type': 'integer', 'default': 20, 'description': 'Number of records per page (max 100)'},
                'ip_address': {'type': 'string', 'default': '', 'description': 'Filter by IP address'},
                'user_id': {'type': 'string', 'default': '', 'description': 'Filter by user ID'},
                'blacklist_type': {'type': 'string', 'default': '', 'description': 'Filter by blacklist type (ip, user, both)'},
                'reason': {'type': 'string', 'default': '', 'description': 'Filter by reason'},
                'is_active': {'type': 'boolean', 'default': True, 'description': 'Filter by active status'},
                'is_permanent': {'type': 'boolean', 'default': None, 'description': 'Filter by permanent status'},
                'created_by': {'type': 'string', 'default': '', 'description': 'Filter by creator'},
                'order_by': {'type': 'string', 'default': '-created_at', 'description': 'Order by field'},
            }
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean', 
                'blacklists': 'list',
                'pagination': 'dict',
                'filters': 'dict',
                'statistics': 'dict'
            },
            description='Blacklist records retrieved successfully',
        ),
    },
)
@api_view(['POST'])
@permission_classes((IsAdminUser,))
@api_search_rate_limit
def GetBlacklist(request):
    try:
        # Get pagination parameters
        page = request.data.get('page', 1)
        page_size = min(request.data.get('page_size', 20), 100)  # Max 100 per page
        
        # Get filter parameters
        ip_address = request.data.get('ip_address', '')
        user_id = request.data.get('user_id', '')
        blacklist_type = request.data.get('blacklist_type', '')
        reason = request.data.get('reason', '')
        is_active = request.data.get('is_active', True)
        is_permanent = request.data.get('is_permanent', None)
        created_by = request.data.get('created_by', '')
        order_by = request.data.get('order_by', '-created_at')
        
        # Validate order_by field
        valid_order_fields = [
            'created_at', '-created_at', 'updated_at', '-updated_at',
            'expires_at', '-expires_at', 'violation_count', '-violation_count',
            'last_violation', '-last_violation'
        ]
        if order_by not in valid_order_fields:
            order_by = '-created_at'
        
        # Build query filters
        filters = {'is_active': is_active}
        
        if ip_address:
            filters['ip_address'] = ip_address
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                filters['user'] = user
            except User.DoesNotExist:
                return JsonResponse({'return': False, 'error': 'User not found'}, status=404)
        
        if blacklist_type:
            if blacklist_type in ['ip', 'user', 'both']:
                filters['blacklist_type'] = blacklist_type
            else:
                return JsonResponse({'return': False, 'error': 'Invalid blacklist_type. Must be ip, user, or both'})
        
        if reason:
            filters['reason'] = reason
        
        if is_permanent is not None:
            filters['is_permanent'] = is_permanent
        
        if created_by:
            filters['created_by'] = created_by
        
        # Get queryset with filters
        queryset = BlackList.objects.filter(**filters).order_by(order_by)
        
        # Calculate pagination
        total_count = queryset.count()
        total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
        
        # Validate page number
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get paginated results
        blacklists = queryset[offset:offset + page_size]
        
        # Calculate statistics
        now = timezone.now()
        stats = {
            'total_entries': total_count,
            'active_entries': queryset.filter(is_active=True).count(),
            'permanent_entries': queryset.filter(is_permanent=True).count(),
            'temporary_entries': queryset.filter(is_permanent=False).count(),
            'expired_entries': queryset.filter(
                is_permanent=False, 
                expires_at__lt=now,
                is_active=True
            ).count(),
            'unique_ips': queryset.filter(ip_address__isnull=False).values('ip_address').distinct().count(),
            'unique_users': queryset.filter(user__isnull=False).values('user').distinct().count(),
            'by_type': {
                'ip': queryset.filter(blacklist_type='ip').count(),
                'user': queryset.filter(blacklist_type='user').count(),
                'both': queryset.filter(blacklist_type='both').count(),
            },
            'by_reason': {}
        }
        
        # Get reason statistics
        reason_stats = queryset.values('reason').annotate(count=models.Count('reason')).order_by('-count')
        for item in reason_stats:
            stats['by_reason'][item['reason']] = item['count']
        
        return JsonResponse({
            'return': True,
            'message': 'Blacklist records retrieved successfully',
            'blacklists': BlackListSerializer(blacklists, many=True).data,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1,
                'next_page': page + 1 if page < total_pages else None,
                'previous_page': page - 1 if page > 1 else None,
            },
            'statistics': stats,
            'filters': {
                'ip_address': ip_address,
                'user_id': user_id,
                'blacklist_type': blacklist_type,
                'reason': reason,
                'is_active': is_active,
                'is_permanent': is_permanent,
                'created_by': created_by,
                'order_by': order_by,
            }
        })
        
    except Exception as e:
        print_log(level='error', message=f'Error getting blacklist list: {str(e)}', 
                 exception_type=e.__class__.__name__, file_path=__file__, 
                 line_number=0, view_name='GetBlacklistList')
        return JsonResponse({'return': False, 'error': str(e)})

###############################################################################################
@extend_schema(
    description='Get paginated list of whitelist records' + '<br><br> <b>Admin Credential</b>' +
    '<br><br> <b>Parameters</b>: This endpoint supports ' +
    '<br> pagination parameters (page, page_size), <br> filter parameters (ip_address, user_id, whitelist_type, reason, is_active, is_permanent, bypass_rate_limits), and sorting (order_by). ' +
    '<br> <b> whitelist_type </b> can be one of the following: ip, user, both.' +
    '<br> <b> is_permanent </b> is a boolean that filters permanent whitelists.' +
    '<br> <b> bypass_rate_limits </b> is a boolean that filters whitelists that bypass rate limits.' +
    '<br> <b> order_by </b> is a string that can be one of the following: -created_at, -updated_at, -expires_at, -violation_count, -last_violation.',
    summary='Get whitelist records with pagination',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'page': {'type': 'integer', 'default': 1, 'description': 'Page number'},
                'page_size': {'type': 'integer', 'default': 20, 'description': 'Number of records per page (max 100)'},
                'ip_address': {'type': 'string', 'default': '', 'description': 'Filter by IP address'},
                'user_id': {'type': 'string', 'default': '', 'description': 'Filter by user ID'},
                'whitelist_type': {'type': 'string', 'default': '', 'description': 'Filter by whitelist type (ip, user, both)'},
                'reason': {'type': 'string', 'default': '', 'description': 'Filter by reason'},
                'is_active': {'type': 'boolean', 'default': True, 'description': 'Filter by active status'},
                'is_permanent': {'type': 'boolean', 'default': None, 'description': 'Filter by permanent status'},
                'bypass_rate_limits': {'type': 'boolean', 'default': None, 'description': 'Filter by rate limit bypass status'},
                'created_by': {'type': 'string', 'default': '', 'description': 'Filter by creator'},
                'order_by': {'type': 'string', 'default': '-created_at', 'description': 'Order by field'},
            }
        }
    },
    responses={
        200: OpenApiResponse(
            response={
                'return': 'boolean', 
                'whitelists': 'list',
                'pagination': 'dict',
                'filters': 'dict',
                'statistics': 'dict'
            },
            description='Whitelist records retrieved successfully',
        ),
    },
)
@api_view(['POST'])
@permission_classes((IsAdminUser,))
@api_search_rate_limit
def GetWhitelist(request):
    try:
        # Get pagination parameters
        page = request.data.get('page', 1)
        page_size = min(request.data.get('page_size', 20), 100)  # Max 100 per page
        
        # Get filter parameters
        ip_address = request.data.get('ip_address', '')
        user_id = request.data.get('user_id', '')
        whitelist_type = request.data.get('whitelist_type', '')
        reason = request.data.get('reason', '')
        is_active = request.data.get('is_active', True)
        is_permanent = request.data.get('is_permanent', None)
        bypass_rate_limits = request.data.get('bypass_rate_limits', None)
        created_by = request.data.get('created_by', '')
        order_by = request.data.get('order_by', '-created_at')
        
        # Validate order_by field
        valid_order_fields = [
            'created_at', '-created_at', 'updated_at', '-updated_at',
            'expires_at', '-expires_at', 'usage_count', '-usage_count',
            'last_used', '-last_used', 'custom_rate_multiplier', '-custom_rate_multiplier'
        ]
        if order_by not in valid_order_fields:
            order_by = '-created_at'
        
        # Build query filters
        filters = {'is_active': is_active}
        
        if ip_address:
            filters['ip_address'] = ip_address
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                filters['user'] = user
            except User.DoesNotExist:
                return JsonResponse({'return': False, 'error': 'User not found'}, status=404)
        
        if whitelist_type:
            if whitelist_type in ['ip', 'user', 'both']:
                filters['whitelist_type'] = whitelist_type
            else:
                return JsonResponse({'return': False, 'error': 'Invalid whitelist_type. Must be ip, user, or both'})
        
        if reason:
            filters['reason'] = reason
        
        if is_permanent is not None:
            filters['is_permanent'] = is_permanent
        
        if bypass_rate_limits is not None:
            filters['bypass_rate_limits'] = bypass_rate_limits
        
        if created_by:
            filters['created_by'] = created_by
        
        # Get queryset with filters
        queryset = WhiteList.objects.filter(**filters).order_by(order_by)
        
        # Calculate pagination
        total_count = queryset.count()
        total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
        
        # Validate page number
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get paginated results
        whitelists = queryset[offset:offset + page_size]
        
        # Calculate statistics
        now = timezone.now()
        stats = {
            'total_entries': total_count,
            'active_entries': queryset.filter(is_active=True).count(),
            'permanent_entries': queryset.filter(is_permanent=True).count(),
            'temporary_entries': queryset.filter(is_permanent=False).count(),
            'expired_entries': queryset.filter(
                is_permanent=False, 
                expires_at__lt=now,
                is_active=True
            ).count(),
            'bypass_enabled': queryset.filter(bypass_rate_limits=True).count(),
            'bypass_disabled': queryset.filter(bypass_rate_limits=False).count(),
            'unique_ips': queryset.filter(ip_address__isnull=False).values('ip_address').distinct().count(),
            'unique_users': queryset.filter(user__isnull=False).values('user').distinct().count(),
            'total_usage': queryset.aggregate(total=models.Sum('usage_count'))['total'] or 0,
            'by_type': {
                'ip': queryset.filter(whitelist_type='ip').count(),
                'user': queryset.filter(whitelist_type='user').count(),
                'both': queryset.filter(whitelist_type='both').count(),
            },
            'by_reason': {}
        }
        
        # Get reason statistics
        reason_stats = queryset.values('reason').annotate(count=models.Count('reason')).order_by('-count')
        for item in reason_stats:
            stats['by_reason'][item['reason']] = item['count']
        
        # Get rate multiplier statistics
        multiplier_stats = queryset.values('custom_rate_multiplier').annotate(
            count=models.Count('custom_rate_multiplier')
        ).order_by('-custom_rate_multiplier')
        stats['by_multiplier'] = {item['custom_rate_multiplier']: item['count'] for item in multiplier_stats}
        
        return JsonResponse({
            'return': True,
            'message': 'Whitelist records retrieved successfully',
            'whitelists': WhiteListSerializer(whitelists, many=True).data,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1,
                'next_page': page + 1 if page < total_pages else None,
                'previous_page': page - 1 if page > 1 else None,
            },
            'statistics': stats,
            'filters': {
                'ip_address': ip_address,
                'user_id': user_id,
                'whitelist_type': whitelist_type,
                'reason': reason,
                'is_active': is_active,
                'is_permanent': is_permanent,
                'bypass_rate_limits': bypass_rate_limits,
                'created_by': created_by,
                'order_by': order_by,
            }
        })
        
    except Exception as e:
        print_log(level='error', message=f'Error getting whitelist list: {str(e)}', 
                 exception_type=e.__class__.__name__, file_path=__file__, 
                 line_number=0, view_name='GetWhitelistList')
        return JsonResponse({'return': False, 'error': str(e)})

###############################################################################################