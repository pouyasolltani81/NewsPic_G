"""
Django views that communicate with the Model Service
"""

import httpx
import asyncio
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .serializers import *
import logging
from AuthModel.models import user_credential
import uuid

logger = logging.getLogger(__name__)

# Model Service URL - configure in settings.py for production
MODEL_SERVICE_URL = "http://localhost:8001"

def run_async(coro):
    """Helper to run async code in sync Django views"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def parse_standard_response(response_data):
    """Parse StandardResponse format from FastAPI service"""
    if isinstance(response_data, dict):
        # Handle the return_ field (comes as "return" in JSON)
        success = response_data.get('return', response_data.get('return_', False))
        data = response_data.get('data', {})
        message = response_data.get('message', '')
        errors = response_data.get('errors', [])
        
        return {
            'success': success,
            'data': data,
            'message': message,
            'errors': errors
        }
    return {
        'success': False,
        'data': {},
        'message': 'Invalid response format',
        'errors': [{'type': 'PARSE_ERROR', 'detail': 'Invalid response format'}]
    }

@extend_schema(
    description='Translate a single text to one or more target languages',
    summary='Translate text',
    methods=['POST'],
    request=TranslationRequestSerializer,
    examples=[
        OpenApiExample(
            'Single Language Translation',
            value={
                "text": "Hello, how are you today?",
                "target_language": "Persian",
                "is_json": False
            },
            request_only=True,
        ),
        OpenApiExample(
            'Multi-Language Translation',
            value={
                "text": "Hello, how are you today?",
                "target_languages": ["Persian", "Spanish", "French"],
                "is_json": False
            },
            request_only=True,
        ),
        OpenApiExample(
            'JSON Translation',
            value={
                "text": '{"title": "Breaking News", "content": "Important announcement"}',
                "target_languages": ["Spanish", "French"],
                "is_json": True
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Translation successful',
            response=TranslationResponseSerializer,
            examples=[
                OpenApiExample(
                    'Successful Multi-Language Translation',
                    value={
                        "return": True,
                        "translations": {
                            "Persian": "سلام، امروز حالت چطور است؟",
                            "Spanish": "Hola, ¿cómo estás hoy?",
                            "French": "Bonjour, comment allez-vous aujourd'hui?"
                        },
                        "original": "Hello, how are you today?",
                        "target_languages": ["Persian", "Spanish", "French"],
                        "successful_languages": ["Persian", "Spanish", "French"]
                    }
                ),
            ]
        ),
        400: OpenApiResponse(description='Bad Request - Invalid parameters'),
        500: OpenApiResponse(description='Internal Server Error'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def translate(request):
    """Translate text endpoint"""
    serializer = TranslationRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # Get target languages as list
            target_languages = serializer.get_target_languages_list()
            
            async def make_request():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate",
                        json={
                            "text": serializer.validated_data['text'],
                            "target_languages": target_languages,
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    response_data = parsed['data']
                    
                    # For backward compatibility: if single language was requested, return simple format
                    if 'target_language' in serializer.validated_data and len(target_languages) == 1:
                        lang = target_languages[0]
                        translations = response_data.get('translations', {})
                        return Response({
                            'return': True,
                            'translation': translations.get(lang),
                            'original': response_data.get('original'),
                            'target_language': lang
                        }, status=status.HTTP_200_OK)
                    
                    # Return full multi-language response
                    response_data['return'] = True
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message'],
                        'details': parsed['errors']
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            else:
                return Response({
                    'return': False,
                    "error": "Model service error",
                    "status_code": response.status_code
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available. Please ensure it is running.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Submit a large text for async translation to multiple languages',
    summary='Async translation for large texts',
    methods=['POST'],
    request=TranslationRequestSerializer,
    examples=[
        OpenApiExample(
            'Large Text Async Translation',
            value={
                "text": "This is a very long text that needs to be translated...",
                "target_languages": ["Persian", "Spanish"],
                "is_json": False
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Translation queued successfully',
            response={
                'type': 'object',
                'properties': {
                    'return': {'type': 'boolean'},
                    'uuid': {'type': 'string', 'description': 'Unique identifier'},
                    'status': {'type': 'string', 'description': 'Processing status'},
                    'estimated_completion_time': {'type': 'string', 'description': 'Estimated completion time'}
                }
            },
            examples=[
                OpenApiExample(
                    'Async Translation Submitted',
                    value={
                        "return": True,
                        "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "status": "processing",
                        "estimated_completion_time": "2024-01-15T10:30:00"
                    }
                ),
            ]
        ),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def translate_async(request):
    """Submit large text for async translation"""
    serializer = TranslationRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # Get target languages as list
            target_languages = serializer.get_target_languages_list()
            
            async def make_request():
                async with httpx.AsyncClient(timeout=None) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate/async",
                        json={
                            "text": serializer.validated_data['text'],
                            "target_languages": target_languages,
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    data = parsed['data']
                    data['return'] = True
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message'],
                        'details': parsed['errors']
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'return': False,
                    "error": "Failed to submit async translation"
                }, status=response.status_code)
                
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Async translation error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Retrieve a previously submitted translation using its UUID (works for both single and batch translations)',
    summary='Get async translation result',
    methods=['GET'],
    parameters=[
        OpenApiParameter(
            name='uuid',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            required=True,
            description='UUID of the translation to retrieve'
        )
    ],
    responses={
        200: OpenApiResponse(
            description='Translation retrieved successfully',
            response={
                'type': 'object',
                'properties': {
                    'return': {'type': 'boolean'},
                    'uuid': {'type': 'string'},
                    'status': {'type': 'string'},
                    'original_text': {'type': 'string'},
                    'translations': {'type': 'object'},
                    'target_languages': {'type': 'array', 'items': {'type': 'string'}},
                    'timestamp': {'type': 'string'}
                }
            }
        ),
        404: OpenApiResponse(description='Translation not found'),
        503: OpenApiResponse(description='Service unavailable')
    }
)
@api_view(['GET'])
@user_credential
def get_async_translation(request, uuid):
    """Retrieve async translation by UUID (handles both single and batch translations)"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/translate/async/{uuid}")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message'],
                    'details': parsed['errors']
                }, status=status.HTTP_400_BAD_REQUEST)
                
        elif response.status_code == 404:
            return Response({
                'return': False,
                "error": f"Translation with UUID {uuid} not found"
            }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'return': False,
                "error": "Failed to retrieve translation"
            }, status=response.status_code)
            
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Get async translation error: {e}")
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Delete a stored translation by UUID',
    summary='Delete async translation',
    methods=['DELETE'],
    parameters=[
        OpenApiParameter(
            name='uuid',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            required=True,
            description='UUID of the translation to delete'
        )
    ],
    responses={
        200: OpenApiResponse(
            description='Translation deleted successfully',
            response={
                'type': 'object',
                'properties': {
                    'return': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'uuid': {'type': 'string'}
                }
            }
        ),
        404: OpenApiResponse(description='Translation not found'),
        503: OpenApiResponse(description='Service unavailable')
    }
)
@api_view(['DELETE'])
@user_credential
def delete_async_translation(request, uuid):
    """Delete async translation by UUID"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(f"{MODEL_SERVICE_URL}/translate/async/{uuid}")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message']
                }, status=status.HTTP_400_BAD_REQUEST)
                
        elif response.status_code == 404:
            return Response({
                'return': False,
                "error": f"Translation with UUID {uuid} not found"
            }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'return': False,
                "error": "Failed to delete translation"
            }, status=response.status_code)
            
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Delete async translation error: {e}")
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='List all stored translation UUIDs and storage statistics',
    summary='List async translations',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='List of translation UUIDs',
            response={
                'type': 'object',
                'properties': {
                    'return': {'type': 'boolean'},
                    'translation_ids': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'count': {'type': 'integer'},
                    'stats': {'type': 'object'}
                }
            }
        ),
        503: OpenApiResponse(description='Service unavailable')
    }
)
@api_view(['GET'])
@user_credential
def list_async_translations(request):
    """List all async translations"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/translate/async")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message']
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'return': False,
                "error": "Failed to list translations"
            }, status=response.status_code)
            
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"List async translations error: {e}")
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Translate multiple texts in batch to multiple languages',
    summary='Batch translation',
    methods=['POST'],
    request=TranslationBatchRequestSerializer,
    examples=[
        OpenApiExample(
            'Batch Translation Example',
            value={
                "texts": [
                    "Good morning",
                    "How are you?",
                    "Thank you very much"
                ],
                "target_languages": ["Spanish", "French"],
                "is_json": False
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Batch translation successful',
            response=BatchTranslationResponseSerializer,
            examples=[
                OpenApiExample(
                    'Successful Batch Translation',
                    value={
                        "return": True,
                        "translations": [
                            {
                                "index": 0,
                                "original": "Good morning",
                                "translations": {
                                    "Spanish": "Buenos días",
                                    "French": "Bonjour"
                                },
                                "success": True,
                                "successful_languages": ["Spanish", "French"]
                            }
                        ],
                        "target_languages": ["Spanish", "French"],
                        "total_texts": 3,
                        "successful": 3,
                        "failed": 0
                    }
                ),
            ]
        ),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def translate_batch(request):
    """Batch translation endpoint"""
    serializer = TranslationBatchRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # Get target languages as list
            target_languages = serializer.get_target_languages_list()
            
            async def make_request():
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate/batch",
                        json={
                            "texts": serializer.validated_data['texts'],
                            "target_languages": target_languages,
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    data = parsed['data']
                    data['return'] = True
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message'],
                        'details': parsed['errors']
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'return': False,
                    "error": "Model service error"
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Batch translation error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Submit multiple texts for async translation to multiple languages',
    summary='Batch async translation',
    methods=['POST'],
    request=TranslationBatchRequestSerializer,
    examples=[
        OpenApiExample(
            'Batch Async Translation Example',
            value={
                "texts": [
                    "This is a long text that needs translation...",
                    "Another long text for translation...",
                    "Third text for async processing..."
                ],
                "target_languages": ["Spanish", "French", "German"],
                "is_json": False
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Batch translation queued successfully',
            response={
                'type': 'object',
                'properties': {
                    'return': {'type': 'boolean'},
                    'uuid': {'type': 'string', 'description': 'Unique identifier for the batch'},
                    'status': {'type': 'string', 'description': 'Processing status'},
                    'text_count': {'type': 'integer', 'description': 'Number of texts in batch'},
                    'target_languages': {'type': 'array', 'items': {'type': 'string'}},
                    'estimated_completion_time': {'type': 'string', 'description': 'Estimated completion time'}
                }
            },
            examples=[
                OpenApiExample(
                    'Batch Async Submitted',
                    value={
                        "return": True,
                        "uuid": "batch-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "status": "processing",
                        "text_count": 3,
                        "target_languages": ["Spanish", "French", "German"],
                        "estimated_completion_time": "2024-01-15T10:35:00"
                    }
                ),
            ]
        ),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def translate_batch_async(request):
    """Submit batch of texts for async translation"""
    serializer = TranslationBatchRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # Get target languages as list
            target_languages = serializer.get_target_languages_list()
            
            async def make_request():
                async with httpx.AsyncClient(timeout=None) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate/batch/async",
                        json={
                            "texts": serializer.validated_data['texts'],
                            "target_languages": target_languages,
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    data = parsed['data']
                    data['return'] = True
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message'],
                        'details': parsed['errors']
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'return': False,
                    "error": "Failed to submit batch async translation"
                }, status=response.status_code)
                
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Batch async translation error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Get list of supported languages for translation',
    summary='Get supported languages',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='Languages retrieved successfully',
            response={
                'type': 'object',
                'properties': {
                    'return': {'type': 'boolean'},
                    'languages': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'count': {'type': 'integer'},
                }
            },
            examples=[
                OpenApiExample(
                    'Supported Languages List',
                    value={
                        "return": True,
                        "languages": [
                            "Arabic", "Bulgarian", "Chinese", "Czech", "Danish", 
                            "Dutch", "English", "Finnish", "French", "German"
                        ],
                        "count": 32
                    }
                ),
            ]
        ),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['GET'])
def get_supported_languages(request):
    """Get supported languages"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/languages")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                # Fallback to hardcoded list
                return Response({
                    'return': True,
                    'languages': [lang[0] for lang in SUPPORTED_LANGUAGES],
                    'count': len(SUPPORTED_LANGUAGES),
                    'note': 'Retrieved from cache'
                }, status=status.HTTP_200_OK)
        else:
            # Return hardcoded list if service error
            return Response({
                'return': True,
                'languages': [lang[0] for lang in SUPPORTED_LANGUAGES],
                'count': len(SUPPORTED_LANGUAGES),
                'note': 'Retrieved from cache as model service is unavailable'
            }, status=status.HTTP_200_OK)
            
    except httpx.ConnectError:
        # Return hardcoded list if service is unavailable
        return Response({
            'return': True,
            'languages': [lang[0] for lang in SUPPORTED_LANGUAGES],
            'count': len(SUPPORTED_LANGUAGES),
            'note': 'Retrieved from cache as model service is unavailable'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Get current configuration',
    summary='Get configuration',
    methods=['GET'],
    responses={
        200: OpenApiResponse(description='Configuration retrieved successfully'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['GET'])
@user_credential
def get_config(request):
    """Get current configuration"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/config")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message']
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'return': False,
                "error": "Model service error"
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Update entire configuration',
    summary='Update configuration',
    methods=['PUT'],
    request=ConfigSerializer,
    responses={
        200: OpenApiResponse(description='Configuration updated successfully'),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['PUT'])
@user_credential
def update_config(request):
    """Update configuration"""
    serializer = ConfigSerializer(data=request.data)
    if serializer.is_valid():
        try:
            async def make_request():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.put(
                        f"{MODEL_SERVICE_URL}/config",
                        json={"config": serializer.validated_data}
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    data = parsed['data']
                    data['return'] = True
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message']
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'return': False,
                    "error": "Model service error"
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Config update error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Update GPU/CPU memory allocation',
    summary='Update memory configuration',
    methods=['PATCH'],
    request=MemoryConfigSerializer,
    responses={
        200: OpenApiResponse(description='Memory configuration updated successfully'),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['PATCH'])
@user_credential
def update_memory_config(request):
    """Update memory configuration"""
    serializer = MemoryConfigSerializer(data=request.data)
    if serializer.is_valid():
        try:
            async def make_request():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.patch(
                        f"{MODEL_SERVICE_URL}/config/memory",
                        json=serializer.validated_data
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    data = parsed['data']
                    data['return'] = True
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message']
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'return': False,
                    "error": "Model service error"
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Memory config update error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Update translation glossary',
    summary='Update glossary',
    methods=['PATCH'],
    request=GlossarySerializer,
    responses={
        200: OpenApiResponse(description='Glossary updated successfully'),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['PATCH'])
@user_credential
def update_glossary(request):
    """Update glossary"""
    serializer = GlossarySerializer(data=request.data)
    if serializer.is_valid():
        try:
            async def make_request():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.patch(
                        f"{MODEL_SERVICE_URL}/config/glossary",
                        json=serializer.validated_data
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    data = parsed['data']
                    data['return'] = True
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message']
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'return': False,
                    "error": "Model service error"
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Glossary update error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Update text generation parameters',
    summary='Update generation parameters',
    methods=['PATCH'],
    request=GenerationParamsSerializer,
    responses={
        200: OpenApiResponse(description='Generation parameters updated successfully'),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['PATCH'])
@user_credential
def update_generation_params(request):
    """Update generation parameters"""
    serializer = GenerationParamsSerializer(data=request.data)
    if serializer.is_valid():
        try:
            async def make_request():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.patch(
                        f"{MODEL_SERVICE_URL}/config/generation",
                        json=serializer.validated_data
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                parsed = parse_standard_response(response.json())
                
                if parsed['success']:
                    data = parsed['data']
                    data['return'] = True
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'return': False,
                        'error': parsed['message']
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'return': False,
                    "error": "Model service error"
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except httpx.ConnectError:
            return Response({
                'return': False,
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Generation params update error: {e}")
            return Response({
                'return': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'return': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Get current memory usage statistics',
    summary='Get memory usage',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='Memory usage retrieved successfully',
            response=MemoryUsageSerializer
        ),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['GET'])
@user_credential
def get_memory_usage(request):
    """Get memory usage"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/memory")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message']
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'return': False,
                "error": "Model service error"
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Reload the model with current configuration',
    summary='Reload model',
    methods=['POST'],
    responses={
        200: OpenApiResponse(description='Model reloaded successfully'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def reload_model(request):
    """Reload model"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{MODEL_SERVICE_URL}/reload")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message'],
                    'details': parsed['errors']
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'return': False,
                "error": "Model service error"
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Delete the entire glossary',
    summary='Delete glossary',
    methods=['DELETE'],
    responses={
        200: OpenApiResponse(description='Glossary deleted successfully'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['DELETE'])
@user_credential
def delete_glossary(request):
    """Delete glossary"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(f"{MODEL_SERVICE_URL}/config/glossary")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message']
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'return': False,
                "error": "Model service error"
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Completely free GPU memory and unload model',
    summary='Free GPU memory',
    methods=['POST'],
    responses={
        200: OpenApiResponse(
            description='GPU memory freed successfully',
            response={
                'type': 'object',
                'properties': {
                    'return': {'type': 'boolean'},
                    'status': {'type': 'string'},
                    'steps': {'type': 'array', 'items': {'type': 'string'}},
                    'gpu_memory_after': {'type': 'object'}
                }
            }
        ),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def free_gpu_memory(request):
    """Free GPU memory completely"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{MODEL_SERVICE_URL}/free_memory")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            
            if parsed['success']:
                data = parsed['data']
                data['return'] = True
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'return': False,
                    'error': parsed['message'],
                    'details': parsed['errors']
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'return': False,
                "error": "Model service error"
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except httpx.ConnectError:
        return Response({
            'return': False,
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'return': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Check if model service is healthy',
    summary='Health check',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='Service is healthy',
            response=HealthCheckSerializer
        ),
    }
)
@api_view(['GET'])
def health_check(request):
    """Check service health"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/health")
                return response
        
        response = run_async(make_request())
        
        if response.status_code == 200:
            parsed = parse_standard_response(response.json())
            model_service_healthy = parsed['success']
            
            return Response({
                'return': True,
                'status': 'healthy' if model_service_healthy else 'degraded',
                'model_service': model_service_healthy,
                'model_service_details': parsed['data'] if model_service_healthy else None
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'return': True,
                'status': 'degraded',
                'model_service': False
            }, status=status.HTTP_200_OK)
    except:
        return Response({
            'return': True,
            'status': 'degraded',
            'model_service': False
        }, status=status.HTTP_200_OK)