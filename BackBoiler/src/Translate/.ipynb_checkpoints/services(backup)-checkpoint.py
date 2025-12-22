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

def parse_service_response(service_response):
    """Parse the standardized response from the model service"""
    try:
        data = service_response.json()
        # Check if it's a standardized response
        if 'return' in data or 'return_' in data:
            success = data.get('return', data.get('return_', False))
            response_data = data.get('data', {})
            message = data.get('message', '')
            errors = data.get('errors', [])
            
            if success:
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': message or 'Request failed',
                    'details': errors,
                    'data': response_data
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Legacy response format
            return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error parsing service response: {e}")
        return Response({
            'error': 'Failed to parse service response',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Translate a single text to multiple target languages',
    summary='Translate text',
    methods=['POST'],
    request=TranslationRequestSerializer,
    examples=[
        OpenApiExample(
            'Multi-language Translation Example',
            value={
                "text": "Hello, how are you today?",
                "target_languages": ["Persian", "Spanish", "French"],
                "is_json": False
            },
            request_only=True,
        ),
        OpenApiExample(
            'JSON Translation Example',
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
            response={
                'type': 'object',
                'properties': {
                    'translations': {
                        'type': 'object',
                        'description': 'Translations keyed by language'
                    },
                    'original': {'type': 'string', 'description': 'Original text'},
                    'target_languages': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Target languages'
                    },
                    'successful_languages': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Successfully translated languages'
                    }
                }
            },
        ),
        400: OpenApiResponse(description='Bad Request'),
        500: OpenApiResponse(description='Internal Server Error'),
        503: OpenApiResponse(description='Model Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def translate(request):
    """Translate text to multiple languages"""
    serializer = TranslationRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            async def make_request():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate",
                        json={
                            "text": serializer.validated_data['text'],
                            "target_languages": serializer.validated_data['target_languages'],
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            return parse_service_response(response)
                
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available. Please ensure it is running.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Submit a large text for async translation to multiple languages',
    summary='Async translation for large texts',
    methods=['POST'],
    request=TranslationRequestSerializer,
    examples=[
        OpenApiExample(
            'Large Text Multi-language Translation',
            value={
                "text": "This is a very long text that needs to be translated...",
                "target_languages": ["Persian", "Spanish", "French"],
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
                    'uuid': {'type': 'string'},
                    'status': {'type': 'string'},
                    'estimated_completion_time': {'type': 'string'}
                }
            }
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
            async def make_request():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate/async",
                        json={
                            "text": serializer.validated_data['text'],
                            "target_languages": serializer.validated_data['target_languages'],
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            return parse_service_response(response)
                
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Async translation error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Retrieve a previously submitted translation using its UUID',
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
                    'uuid': {'type': 'string'},
                    'status': {'type': 'string'},
                    'original_text': {'type': 'string'},
                    'translations': {'type': 'object'},
                    'target_languages': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
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
    """Retrieve async translation by UUID"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/translate/async/{uuid}")
                return response
        
        response = run_async(make_request())
        return parse_service_response(response)
            
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Get async translation error: {e}")
        return Response({
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
        200: OpenApiResponse(description='Translation deleted successfully'),
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
        return parse_service_response(response)
            
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Delete async translation error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='List all stored translation UUIDs',
    summary='List async translations',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='List of translation UUIDs',
            response={
                'type': 'object',
                'properties': {
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
        return parse_service_response(response)
            
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"List async translations error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Translate multiple texts to multiple languages in batch',
    summary='Batch translation',
    methods=['POST'],
    request=TranslationBatchRequestSerializer,
    examples=[
        OpenApiExample(
            'Batch Multi-language Translation',
            value={
                "texts": [
                    "Good morning",
                    "How are you?",
                    "Thank you very much"
                ],
                "target_languages": ["Spanish", "French", "German"],
                "is_json": False
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(description='Batch translation successful'),
        400: OpenApiResponse(description='Bad Request'),
        500: OpenApiResponse(description='Internal Server Error'),
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
            async def make_request():
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate/batch",
                        json={
                            "texts": serializer.validated_data['texts'],
                            "target_languages": serializer.validated_data['target_languages'],
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            return parse_service_response(response)
                
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Batch translation error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Submit multiple texts for async batch translation',
    summary='Async batch translation',
    methods=['POST'],
    request=TranslationBatchRequestSerializer,
    responses={
        200: OpenApiResponse(
            description='Batch translation queued successfully',
            response={
                'type': 'object',
                'properties': {
                    'uuid': {'type': 'string'},
                    'status': {'type': 'string'},
                    'text_count': {'type': 'integer'},
                    'target_languages': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'estimated_completion_time': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Bad Request'),
        503: OpenApiResponse(description='Service Unavailable'),
    }
)
@api_view(['POST'])
@user_credential
def translate_batch_async(request):
    """Submit batch for async translation"""
    serializer = TranslationBatchRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            async def make_request():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate/batch/async",
                        json={
                            "texts": serializer.validated_data['texts'],
                            "target_languages": serializer.validated_data['target_languages'],
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            return parse_service_response(response)
                
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Batch async translation error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
                    'languages': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'count': {'type': 'integer'}
                }
            }
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
        return parse_service_response(response)
        
    except httpx.ConnectError:
        # Return hardcoded list if service is unavailable
        return Response({
            'languages': [
                "Arabic", "Bulgarian", "Chinese", "Czech", "Danish", 
                "Dutch", "English", "Finnish", "French", "German",
                "Greek", "Gujarati", "Hebrew", "Hindi", "Hungarian",
                "Indonesian", "Italian", "Japanese", "Korean", "Persian",
                "Polish", "Portuguese", "Romanian", "Russian", "Slovak",
                "Spanish", "Swedish", "Tagalog", "Thai", "Turkish",
                "Ukrainian", "Vietnamese"
            ],
            'count': 32,
            'note': 'Retrieved from cache as model service is unavailable'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Get memory usage statistics',
    summary='Get memory usage',
    methods=['GET'],
    responses={
        200: OpenApiResponse(description='Memory usage retrieved successfully'),
        500: OpenApiResponse(description='Internal Server Error'),
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
        return parse_service_response(response)
        
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Get translation service statistics',
    summary='Get service stats',
    methods=['GET'],
    responses={
        200: OpenApiResponse(description='Statistics retrieved successfully'),
        503: OpenApiResponse(description='Service unavailable'),
    }
)
@api_view(['GET'])
@user_credential
def get_stats(request):
    """Get service statistics"""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{MODEL_SERVICE_URL}/stats")
                return response
        
        response = run_async(make_request())
        return parse_service_response(response)
        
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Reload the model',
    summary='Reload model',
    methods=['POST'],
    responses={
        200: OpenApiResponse(description='Model reloaded successfully'),
        500: OpenApiResponse(description='Internal Server Error'),
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
        return parse_service_response(response)
        
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Free GPU memory',
    summary='Free GPU memory',
    methods=['POST'],
    responses={
        200: OpenApiResponse(description='GPU memory freed successfully'),
        500: OpenApiResponse(description='Internal Server Error'),
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
        return parse_service_response(response)
        
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Check if model service is healthy',
    summary='Health check',
    methods=['GET'],
    responses={
        200: OpenApiResponse(description='Service health status'),
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
            data = response.json()
            # Parse standardized response
            if 'return' in data or 'return_' in data:
                success = data.get('return', data.get('return_', False))
                health_data = data.get('data', {})
                return Response({
                    'status': 'healthy' if success else 'degraded',
                    'model_service': success,
                    'model_service_details': health_data
                }, status=status.HTTP_200_OK)
            else:
                # Legacy format
                return Response({
                    'status': 'healthy',
                    'model_service': True,
                    'model_service_details': data
                }, status=status.HTTP_200_OK)
    except:
        return Response({
            'status': 'degraded',
            'model_service': False,
            'model_service_details': None
        }, status=status.HTTP_200_OK)