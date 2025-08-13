from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
import sys
import os
from django.apps import apps


# @permission_classes([IsAuthenticated])
from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
import os, json
from datetime import datetime
import requests
from django.conf import settings
from django.utils import translation
from django.apps import apps
import logging
import traceback
import torch

logger = logging.getLogger(__name__)

# Global variables for testing
_test_model = None
_test_tokenizer = None


@extend_schema(
    description='Translate text to target language using small100 multilingual model',
    summary='Translate text between 100+ languages',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'text': {
                    'type': 'string',
                    'description': 'Text to translate',
                    'example': 'जीवन एक चॉकलेट बॉक्स की तरह है।'
                },
                'target_lang': {
                    'type': 'string',
                    'description': 'Target language code (e.g., en, fr, es, zh, ar, hi, etc.)',
                    'example': 'fr'
                },
                'source_lang': {
                    'type': 'string',
                    'description': 'Source language code (optional - model will auto-detect)',
                    'example': 'hi',
                    'required': False
                }
            },
            'required': ['text', 'target_lang'],
        }
    },
    responses={
        200: OpenApiResponse(
            description='Translation results',
            response={
                'type': 'object',
                'properties': {
                    'original_text': {'type': 'string'},
                    'translated_text': {'type': 'string'},
                    'source_lang': {'type': 'string'},
                    'target_lang': {'type': 'string'},
                    'model_used': {'type': 'string'}
                }
            }
        ),
    }
)

@api_view(['POST'])
@permission_classes([AllowAny])  # Temporarily allow any for testing
def translate_text(request):
    """Translate text using M2M100 multilingual model"""
    
    global _test_model, _test_tokenizer
    
    try:
        # Log incoming request
        logger.info(f"Translation request received: {request.data}")
        
        # Get parameters
        text = request.data.get('text', '').strip()
        target_lang = request.data.get('target_lang', '').strip().lower()
        source_lang = request.data.get('source_lang', '').strip().lower()
        
        logger.info(f"Parameters: text='{text}', target_lang='{target_lang}', source_lang='{source_lang}'")
        
        # Validate parameters
        if not text:
            return Response({
                'success': False,
                'error': "Missing 'text' parameter"
            }, status=400)
        
        if not target_lang:
            return Response({
                'success': False,
                'error': "Missing 'target_lang' parameter"
            }, status=400)
        
        # List of supported language codes for M2M100
        supported_langs = [
            'af', 'am', 'ar', 'ast', 'az', 'ba', 'be', 'bg', 'bn', 'br', 'bs', 'ca', 'ceb', 'cs', 'cy', 'da', 
            'de', 'el', 'en', 'es', 'et', 'fa', 'ff', 'fi', 'fr', 'fy', 'ga', 'gd', 'gl', 'gu', 'ha', 'he', 
            'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'ig', 'ilo', 'is', 'it', 'ja', 'jv', 'ka', 'kk', 'km', 'kn', 
            'ko', 'lb', 'lg', 'ln', 'lo', 'lt', 'lv', 'mg', 'mk', 'ml', 'mn', 'mr', 'ms', 'my', 'ne', 'nl', 
            'no', 'ns', 'oc', 'or', 'pa', 'pl', 'ps', 'pt', 'ro', 'ru', 'sd', 'si', 'sk', 'sl', 'so', 'sq', 
            'sr', 'ss', 'su', 'sv', 'sw', 'ta', 'th', 'tl', 'tn', 'tr', 'uk', 'ur', 'uz', 'vi', 'wo', 'xh', 
            'yi', 'yo', 'zh', 'zu'
        ]
        
        if target_lang not in supported_langs:
            return Response({
                'success': False,
                'error': f"Unsupported target language: {target_lang}",
                'supported_languages': supported_langs
            }, status=400)
        
        if source_lang and source_lang not in supported_langs:
            return Response({
                'success': False,
                'error': f"Unsupported source language: {source_lang}",
                'supported_languages': supported_langs
            }, status=400)
        
        # TESTING: Load model directly in view if not already loaded
        if _test_model is None or _test_tokenizer is None:
            logger.info("Loading model directly in view for testing...")
            
            try:
                from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
                
                model_path = "/home/anews/PS/translate/m2m100_418M"
                
                # Check if path exists
                if not os.path.exists(model_path):
                    return Response({
                        'success': False,
                        'error': f"Model path does not exist: {model_path}"
                    }, status=500)
                
                # Check if it's a directory with model files
                model_files = os.listdir(model_path)
                logger.info(f"Files in model directory: {model_files}")
                
                # Load model and tokenizer
                logger.info("Loading M2M100 model...")
                _test_model = M2M100ForConditionalGeneration.from_pretrained(model_path)
                
                logger.info("Loading M2M100 tokenizer...")
                _test_tokenizer = M2M100Tokenizer.from_pretrained(model_path)
                
                logger.info("Model and tokenizer loaded successfully!")
                
                # Log model info
                logger.info(f"Model type: {type(_test_model)}")
                logger.info(f"Tokenizer type: {type(_test_tokenizer)}")
                logger.info(f"Model device: {next(_test_model.parameters()).device}")
                
            except Exception as load_error:
                logger.error(f"Failed to load model: {load_error}")
                logger.error(traceback.format_exc())
                return Response({
                    'success': False,
                    'error': f"Failed to load model: {str(load_error)}",
                    'traceback': traceback.format_exc()
                }, status=500)
        
        model = _test_model
        tokenizer = _test_tokenizer
        
        logger.info("Creating tokenizer instance...")
        
        # Set source language
        if source_lang:
            tokenizer.src_lang = source_lang
        else:
            tokenizer.src_lang = 'en'
        
        logger.info(f"Tokenizing with src_lang={tokenizer.src_lang}")
        
        # Tokenize
        encoded_text = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        logger.info(f"Encoded text shape: {encoded_text['input_ids'].shape}")
        
        # Get target language ID
        target_lang_id = tokenizer.get_lang_id(target_lang)
        logger.info(f"Target language ID: {target_lang_id}")
        
        # Move to same device as model if using GPU
        device = next(model.parameters()).device
        encoded_text = {k: v.to(device) for k, v in encoded_text.items()}
        
        # Generate translation
        logger.info("Generating translation...")
        with torch.no_grad():  # Disable gradient computation for inference
            generated_tokens = model.generate(
                **encoded_text,
                forced_bos_token_id=target_lang_id,
                max_length=512,
                num_beams=5,
                length_penalty=1.0,
                early_stopping=True,
                no_repeat_ngram_size=3,
                temperature=1.0,
            )
        
        logger.info(f"Generated tokens shape: {generated_tokens.shape}")
        
        # Decode
        logger.info("Decoding translation...")
        translated_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        
        logger.info(f"Translation successful: '{text}' -> '{translated_text}'")
        
        return Response({
            'success': True,
            'data': {
                'original_text': text,
                'translated_text': translated_text,
                'source_lang': source_lang if source_lang else tokenizer.src_lang,
                'target_lang': target_lang,
                'model_used': 'm2m100_418M',
                'loaded_in_view': True  # Indicator that model was loaded in view
            }
        }, status=200)
        
    except Exception as e:
        logger.error(f"Translation error: {type(e).__name__}: {str(e)}")
        logger.error(traceback.format_exc())
        
        return Response({
            'success': False,
            'error': f"Translation failed: {type(e).__name__}: {str(e)}",
            'traceback': traceback.format_exc()  # Remove this in production
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_model_status(request):
    """Check if the translation model is loaded"""
    global _test_model, _test_tokenizer
    
    try:
        # Check both AppConfig and view-loaded models
        app_config = apps.get_app_config('Translate')
        
        app_model = None
        app_tokenizer = None
        
        if hasattr(app_config, 'get_model_and_tokenizer'):
            try:
                app_model, app_tokenizer = app_config.get_model_and_tokenizer()
            except:
                pass
        else:
            app_model = getattr(app_config, 'model', None)
            app_tokenizer = getattr(app_config, 'tokenizer', None)
        
        # Check model path
        model_path = "/home/anews/PS/translate/m2m100_418M"
        path_exists = os.path.exists(model_path)
        model_files = []
        if path_exists:
            model_files = os.listdir(model_path)
        
        return Response({
            'success': True,
            'app_config': {
                'model_loaded': app_model is not None,
                'tokenizer_loaded': app_tokenizer is not None,
                'model_type': str(type(app_model)) if app_model else None,
                'tokenizer_type': str(type(app_tokenizer)) if app_tokenizer else None,
            },
            'view_loaded': {
                'model_loaded': _test_model is not None,
                'tokenizer_loaded': _test_tokenizer is not None,
                'model_type': str(type(_test_model)) if _test_model else None,
                'tokenizer_type': str(type(_test_tokenizer)) if _test_tokenizer else None,
            },
            'model_path': {
                'path': model_path,
                'exists': path_exists,
                'files': model_files[:10] if model_files else []  # Show first 10 files
            },
            'cuda_available': torch.cuda.is_available(),
            'device': str(next(_test_model.parameters()).device) if _test_model else None
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def test_simple_translation(request):
    """Simple test endpoint to verify basic functionality"""
    try:
        # Just echo back the input with a simple transformation
        text = request.data.get('text', '')
        target_lang = request.data.get('target_lang', 'en')
        
        # Simple mock translation for testing
        mock_translations = {
            'fr': {'hello': 'bonjour', 'world': 'monde'},
            'es': {'hello': 'hola', 'world': 'mundo'},
            'de': {'hello': 'hallo', 'world': 'welt'},
        }
        
        words = text.lower().split()
        translated_words = []
        
        for word in words:
            if target_lang in mock_translations and word in mock_translations[target_lang]:
                translated_words.append(mock_translations[target_lang][word])
            else:
                translated_words.append(word)
        
        return Response({
            'success': True,
            'data': {
                'original_text': text,
                'translated_text': ' '.join(translated_words),
                'target_lang': target_lang,
                'note': 'This is a mock translation for testing'
            }
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
# Optional: Add a service to list supported languages
@extend_schema(
    description='Get list of supported languages for translation',
    summary='List all supported language codes',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='List of supported languages',
            response={
                'type': 'object',
                'properties': {
                    'languages': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'code': {'type': 'string'},
                                'name': {'type': 'string'}
                            }
                        }
                    },
                    'total': {'type': 'integer'}
                }
            }
        ),
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def list_supported_languages(request):
    """Get list of supported languages"""
    
    # Language code to name mapping
    language_map = {
        'af': 'Afrikaans', 'am': 'Amharic', 'ar': 'Arabic', 'ast': 'Asturian', 
        'az': 'Azerbaijani', 'ba': 'Bashkir', 'be': 'Belarusian', 'bg': 'Bulgarian',
        'bn': 'Bengali', 'br': 'Breton', 'bs': 'Bosnian', 'ca': 'Catalan',
        'ceb': 'Cebuano', 'cs': 'Czech', 'cy': 'Welsh', 'da': 'Danish',
        'de': 'German', 'el': 'Greek', 'en': 'English', 'es': 'Spanish',
        'et': 'Estonian', 'fa': 'Persian', 'ff': 'Fulah', 'fi': 'Finnish',
        'fr': 'French', 'fy': 'Western Frisian', 'ga': 'Irish', 'gd': 'Scottish Gaelic',
        'gl': 'Galician', 'gu': 'Gujarati', 'ha': 'Hausa', 'he': 'Hebrew',
        'hi': 'Hindi', 'hr': 'Croatian', 'ht': 'Haitian', 'hu': 'Hungarian',
        'hy': 'Armenian', 'id': 'Indonesian', 'ig': 'Igbo', 'ilo': 'Iloko',
        'is': 'Icelandic', 'it': 'Italian', 'ja': 'Japanese', 'jv': 'Javanese',
        'ka': 'Georgian', 'kk': 'Kazakh', 'km': 'Khmer', 'kn': 'Kannada',
        'ko': 'Korean', 'lb': 'Luxembourgish', 'lg': 'Ganda', 'ln': 'Lingala',
        'lo': 'Lao', 'lt': 'Lithuanian', 'lv': 'Latvian', 'mg': 'Malagasy',
        'mk': 'Macedonian', 'ml': 'Malayalam', 'mn': 'Mongolian', 'mr': 'Marathi',
        'ms': 'Malay', 'my': 'Burmese', 'ne': 'Nepali', 'nl': 'Dutch',
        'no': 'Norwegian', 'ns': 'Northern Sotho', 'oc': 'Occitan', 'or': 'Oriya',
        'pa': 'Punjabi', 'pl': 'Polish', 'ps': 'Pashto', 'pt': 'Portuguese',
        'ro': 'Romanian', 'ru': 'Russian', 'sd': 'Sindhi', 'si': 'Sinhala',
        'sk': 'Slovak', 'sl': 'Slovenian', 'so': 'Somali', 'sq': 'Albanian',
        'sr': 'Serbian', 'ss': 'Swati', 'su': 'Sundanese', 'sv': 'Swedish',
        'sw': 'Swahili', 'ta': 'Tamil', 'th': 'Thai', 'tl': 'Tagalog',
        'tn': 'Tswana', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu',
        'uz': 'Uzbek', 'vi': 'Vietnamese', 'wo': 'Wolof', 'xh': 'Xhosa',
        'yi': 'Yiddish', 'yo': 'Yoruba', 'zh': 'Chinese', 'zu': 'Zulu'
    }
    
    languages = [{'code': code, 'name': name} for code, name in language_map.items()]
    
    return Response({
        'return': True,
        'languages': languages,
        'total': len(languages)
    })