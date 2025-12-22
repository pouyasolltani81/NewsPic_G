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

@extend_schema(
    description='Translate a single text to a target language',
    summary='Translate text',
    methods=['POST'],
    request=TranslationRequestSerializer,
    examples=[
        OpenApiExample(
            'English to Persian Example',
            value={
                "text": "Hello, how are you today?",
                "target_language": "Persian",
                "is_json": False
            },
            request_only=True,
            response_only=False,
        ),
        OpenApiExample(
            'JSON Translation Example',
            value={
                "text": '{"title": "Breaking News", "content": "Important announcement"}',
                "target_language": "Spanish",
                "is_json": True
            },
            request_only=True,
            response_only=False,
        ),
        OpenApiExample(
            'Complex Text Translation',
            value={
                "text": "The artificial intelligence conference will be held next month in San Francisco.",
                "target_language": "French",
                "is_json": False
            },
            request_only=True,
            response_only=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Translation successful',
            response={
                'type': 'object',
                'properties': {
                    'translation': {'type': 'string', 'description': 'Translated text'},
                    'original': {'type': 'string', 'description': 'Original text'},
                    'target_language': {'type': 'string', 'description': 'Target language used'},
                }
            },
            examples=[
                OpenApiExample(
                    'Successful Translation',
                    value={
                        "translation": "سلام، امروز حالت چطور است؟",
                        "original": "Hello, how are you today?",
                        "target_language": "Persian"
                    }
                ),
            ]
        ),
        400: OpenApiResponse(description='Bad Request - Invalid language or parameters'),
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
            async def make_request():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate",
                        json={
                            "text": serializer.validated_data['text'],
                            "target_language": serializer.validated_data['target_language'],
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            elif response.status_code == 400:
                return Response(
                    {"error": "Invalid request", "details": response.json()},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {"error": "Model service error", "details": response.text},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
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

# NEW: Async translation for big texts
@extend_schema(
    description='Submit a large text for translation and receive a UUID to retrieve it later. Ideal for texts that may take a long time to translate.',
    summary='Async translation for large texts',
    methods=['POST'],
    request=TranslationRequestSerializer,
    examples=[
        OpenApiExample(
            'Large Text Translation Example',
            value={
                "text": "This is a very long text that needs to be translated and may take significant time to process...",
                "target_language": "Persian",
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
                    'uuid': {
                        'type': 'string',
                        'description': 'Unique identifier for retrieving the translation'
                    },
                    'status': {
                        'type': 'string',
                        'description': 'Current status of the translation'
                    },
                    'message': {
                        'type': 'string',
                        'description': 'Status message'
                    }
                }
            },
            examples=[
                OpenApiExample(
                    'Successful Async Submission',
                    value={
                        "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "status": "completed",
                        "message": "Translation completed and saved successfully"
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
            async def make_request():
                async with httpx.AsyncClient(timeout=None) as client:  # No timeout for async
                    response = await client.post(
                        f"{MODEL_SERVICE_URL}/translate/async",
                        json={
                            "text": serializer.validated_data['text'],
                            "target_language": serializer.validated_data['target_language'],
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                error_data = response.json() if response.text else {"error": "Unknown error"}
                return Response(
                    {"error": "Failed to submit async translation", "details": error_data},
                    status=response.status_code
                )
                
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

# NEW: Get async translation by UUID
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
                    'translation': {'type': 'string'},
                    'target_language': {'type': 'string'},
                    'timestamp': {'type': 'string'},
                    'metadata': {'type': 'object'}
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
        
        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        elif response.status_code == 404:
            return Response(
                {"error": f"Translation with UUID {uuid} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        else:
            return Response(
                {"error": "Failed to retrieve translation", "details": response.text},
                status=response.status_code
            )
            
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Get async translation error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# NEW: Delete async translation
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
            return Response(response.json(), status=status.HTTP_200_OK)
        elif response.status_code == 404:
            return Response(
                {"error": f"Translation with UUID {uuid} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        else:
            return Response(
                {"error": "Failed to delete translation", "details": response.text},
                status=response.status_code
            )
            
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Delete async translation error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# NEW: List all async translations
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
                    'translation_ids': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'List of translation UUIDs'
                    },
                    'count': {
                        'type': 'integer',
                        'description': 'Total number of stored translations'
                    },
                    'stats': {
                        'type': 'object',
                        'properties': {
                            'total_translations': {'type': 'integer'},
                            'max_translations': {'type': 'integer'},
                            'storage_file': {'type': 'string'},
                            'oldest_translation': {'type': 'string'},
                            'newest_translation': {'type': 'string'}
                        }
                    }
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
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Failed to list translations", "details": response.text},
                status=response.status_code
            )
            
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
    description='Translate multiple texts in batch to a target language',
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
                "target_language": "Spanish",
                "is_json": False
            },
            request_only=True,
            response_only=False,
        ),
        OpenApiExample(
            'JSON Batch Translation',
            value={
                "texts": [
                    '{"name": "John", "message": "Hello"}',
                    '{"name": "Jane", "message": "Goodbye"}'
                ],
                "target_language": "French",
                "is_json": True
            },
            request_only=True,
            response_only=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Batch translation successful',
            response={
                'type': 'object',
                'properties': {
                    'translations': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'original': {'type': 'string'},
                                'translation': {'type': 'string'},
                            }
                        }
                    },
                    'target_language': {'type': 'string'},
                    'count': {'type': 'integer'},
                }
            },
            examples=[
                OpenApiExample(
                    'Successful Batch Translation',
                    value={
                        "translations": [
                            {"original": "Good morning", "translation": "Buenos días"},
                            {"original": "How are you?", "translation": "¿Cómo estás?"},
                            {"original": "Thank you very much", "translation": "Muchas gracias"}
                        ],
                        "target_language": "Spanish",
                        "count": 3
                    }
                ),
            ]
        ),
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
                            "target_language": serializer.validated_data['target_language'],
                            "is_json": serializer.validated_data.get('is_json', False)
                        }
                    )
                    return response
            
            response = run_async(make_request())
            
            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            elif response.status_code == 400:
                return Response(
                    {"error": "Invalid request", "details": response.json()},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {"error": "Model service error", "details": response.text},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
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
                    'count': {'type': 'integer'},
                }
            },
            examples=[
                OpenApiExample(
                    'Supported Languages List',
                    value={
                        "languages": [
                            "Arabic", "Bulgarian", "Chinese", "Czech", "Danish", 
                            "Dutch", "English", "Finnish", "French", "German",
                            "Greek", "Gujarati", "Hebrew", "Hindi", "Hungarian",
                            "Indonesian", "Italian", "Japanese", "Korean", "Persian",
                            "Polish", "Portuguese", "Romanian", "Russian", "Slovak",
                            "Spanish", "Swedish", "Tagalog", "Thai", "Turkish",
                            "Ukrainian", "Vietnamese"
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
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Model service error"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
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
    description='Get current configuration',
    summary='Get configuration',
    methods=['GET'],
    responses={
        200: OpenApiResponse(description='Configuration retrieved successfully'),
        500: OpenApiResponse(description='Internal Server Error'),
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
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Model service error"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Update entire configuration',
    summary='Update configuration',
    methods=['PUT'],
    request=ConfigSerializer,
    examples=[
        OpenApiExample(
            'Configuration Update Example',
            value={
                "model": {
                    "model_id": "aya-23-8B",
                    "torch_dtype": "bfloat16",
                    "device_map": "auto",
                    "max_memory": {
                        "gpu": "20GB",
                        "cpu": "30GB"
                    },
                    "offload_folder": "offload",
                    "offload_state_dict": True,
                    "low_cpu_mem_usage": True
                },
                "translation": {
                    "target_language": "Persian",
                    "context": {
                        "domain": "news",
                        "style": "formal"
                    },
                    "generation_params": {
                        "max_new_tokens": 128,
                        "temperature": 0.7,
                        "do_sample": True,
                        "top_p": 0.9
                    }
                },
                "glossary": {
                    "AI": "هوش مصنوعی",
                    "Computer": "رایانه"
                }
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Configuration updated successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'config': {'type': 'object'},
                }
            }
        ),
        400: OpenApiResponse(description='Bad Request'),
        500: OpenApiResponse(description='Internal Server Error'),
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
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Model service error", "details": response.text},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Config update error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Update GPU/CPU memory allocation',
    summary='Update memory configuration',
    methods=['PATCH'],
    request=MemoryConfigSerializer,
    examples=[
        OpenApiExample(
            'Memory Configuration Example',
            value={
                "gpu_memory": "24GB",
                "cpu_memory": "32GB"
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Memory configuration updated successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'gpu_memory': {'type': 'string'},
                    'cpu_memory': {'type': 'string'},
                }
            }
        ),
        400: OpenApiResponse(description='Bad Request'),
        500: OpenApiResponse(description='Internal Server Error'),
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
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Model service error", "details": response.text},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Memory config update error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Update translation glossary',
    summary='Update glossary',
    methods=['PATCH'],
    request=GlossarySerializer,
    examples=[
        OpenApiExample(
            'Glossary Update Example',
            value={
                "terms": {
                    "AI": "هوش مصنوعی",
                    "Machine Learning": "یادگیری ماشین",
                    "Deep Learning": "یادگیری عمیق",
                    "Neural Network": "شبکه عصبی",
                    "Computer": "رایانه"
                }
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Glossary updated successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'glossary': {'type': 'object'},
                }
            }
        ),
        400: OpenApiResponse(description='Bad Request'),
        500: OpenApiResponse(description='Internal Server Error'),
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
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Model service error", "details": response.text},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Glossary update error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Update text generation parameters',
    summary='Update generation parameters',
    methods=['PATCH'],
    request=GenerationParamsSerializer,
    examples=[
        OpenApiExample(
            'Generation Parameters Example',
            value={
                "max_new_tokens": 256,
                "temperature": 0.8,
                "do_sample": True,
                "top_p": 0.95,
                "top_k": 50
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Generation parameters updated successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'params': {'type': 'object'},
                }
            }
        ),
        400: OpenApiResponse(description='Bad Request'),
        500: OpenApiResponse(description='Internal Server Error'),
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
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Model service error", "details": response.text},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        except httpx.ConnectError:
            return Response({
                'error': 'Model service is not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Generation params update error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description='Get current memory usage statistics',
    summary='Get memory usage',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='Memory usage retrieved successfully',
            response={
                'type': 'object',
                'properties': {
                    'is_model_loaded': {'type': 'boolean'},
                    'is_tokenizer_loaded': {'type': 'boolean'},
                    'gpu_allocated_gb': {'type': 'number'},
                    'gpu_reserved_gb': {'type': 'number'},
                    'gpu_total_gb': {'type': 'number'},
                    'cpu_memory_gb': {'type': 'number'},
                    'cpu_percent': {'type': 'number'},
                }
            }
        ),
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
        
        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Model service error"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Reload the model with current configuration',
    summary='Reload model',
    methods=['POST'],
    responses={
        200: OpenApiResponse(
            description='Model reloaded successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                }
            }
        ),
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
        
        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Model service error", "details": response.text},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    description='Delete the entire glossary',
    summary='Delete glossary',
    methods=['DELETE'],
    responses={
        200: OpenApiResponse(
            description='Glossary deleted successfully',
            response={
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                }
            }
        ),
        500: OpenApiResponse(description='Internal Server Error'),
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
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Model service error", "details": response.text},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    except httpx.ConnectError:
        return Response({
            'error': 'Model service is not available'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
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
                    'status': {'type': 'string'},
                    'steps': {'type': 'array', 'items': {'type': 'string'}},
                    'gpu_memory_after': {
                        'type': 'object',
                        'properties': {
                            'allocated_gb': {'type': 'number'},
                            'reserved_gb': {'type': 'number'},
                        }
                    }
                }
            }
        ),
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
        
        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Model service error", "details": response.text},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
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
        200: OpenApiResponse(
            description='Service is healthy',
            response={
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'model_service': {'type': 'boolean'},
                    'model_service_details': {
                        'type': 'object',
                        'properties': {
                            'status': {'type': 'string'},
                            'model_loaded': {'type': 'boolean'},
                            'supported_languages': {
                                'type': 'array',
                                'items': {'type': 'string'}
                            }
                        }
                    }
                }
            }
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
        model_service_healthy = response.status_code == 200
        
        return Response({
            'status': 'healthy' if model_service_healthy else 'degraded',
            'model_service': model_service_healthy,
            'model_service_details': response.json() if model_service_healthy else None
        }, status=status.HTTP_200_OK)
    except:
        return Response({
            'status': 'degraded',
            'model_service': False
        }, status=status.HTTP_200_OK)