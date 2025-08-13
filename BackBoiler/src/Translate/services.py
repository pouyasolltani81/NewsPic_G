from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
import sys
import os
from django.apps import apps

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
# @permission_classes([IsAuthenticated])
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # or [AllowAny] depending on your needs
def translate_text(request):
    """Translate text using M2M100 multilingual model"""
    
    # Get parameters
    text = request.data.get('text', '').strip()
    target_lang = request.data.get('target_lang', '').strip().lower()
    source_lang = request.data.get('source_lang', '').strip().lower()
    
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
    
    try:
        # Get the pre-loaded model and tokenizer using lazy loading
        app_config = apps.get_app_config('Translate')
        model, tokenizer = app_config.get_model_and_tokenizer()
        
        if model is None or tokenizer is None:
            return Response({
                'success': False,
                'error': "Translation model not loaded. Please restart the server."
            }, status=500)
        
        # Create a fresh tokenizer instance for thread safety
        from transformers import M2M100Tokenizer
        tokenizer_fresh = M2M100Tokenizer.from_pretrained(tokenizer.name_or_path)
        
        # Set source language (default to 'en' if not provided)
        if source_lang:
            tokenizer_fresh.src_lang = source_lang
        else:
            tokenizer_fresh.src_lang = 'en'  # Default source language
        
        # Tokenize the input text
        encoded_text = tokenizer_fresh(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        
        # Get the target language ID for forced_bos_token_id
        target_lang_id = tokenizer_fresh.get_lang_id(target_lang)
        
        # Generate translation with forced target language
        generated_tokens = model.generate(
            **encoded_text,
            forced_bos_token_id=target_lang_id,
            max_length=512,
            num_beams=5,
            length_penalty=1.0,
            early_stopping=True,
            no_repeat_ngram_size=3,  # Prevent repetition
            temperature=1.0,  # Control randomness
        )
        
        # Decode the translation
        translated_text = tokenizer_fresh.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        
        # Log for debugging
        print(f"Translation: '{text}' ({tokenizer_fresh.src_lang}) -> '{translated_text}' ({target_lang})")
        
        return Response({
            'retuen': True,
            'data': {
                'original_text': text,
                'translated_text': translated_text,
                'source_lang': source_lang if source_lang else tokenizer_fresh.src_lang,
                'target_lang': target_lang,
                'model_used': 'm2m100_418M'
            }
        }, status=200)
        
    except AttributeError as e:
        print(f"AttributeError: {e}")
        return Response({
            'retuen': False,
            'error': f"Model configuration error: {str(e)}. Make sure you're using M2M100 model and tokenizer."
        }, status=500)
        
    except Exception as e:
        print(f"Translation error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'retuen': False,
            'error': f"Translation failed: {str(e)}"
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