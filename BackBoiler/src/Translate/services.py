from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
import sys
import os





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
@permission_classes([IsAuthenticated])  # or [AllowAny] depending on your needs
def translate_text(request):
    """Translate text using small100 multilingual model"""
    
    # Get parameters
    text = request.data.get('text', '').strip()
    target_lang = request.data.get('target_lang', '').strip().lower()
    source_lang = request.data.get('source_lang', '').strip().lower()
    
    # Validate parameters
    if not text:
        return Response({'error': "Missing 'text' parameter"}, status=400)
    
    if not target_lang:
        return Response({'error': "Missing 'target_lang' parameter"}, status=400)
    
    # List of supported language codes (you can expand this)
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
            'error': f"Unsupported target language: {target_lang}",
            'supported_languages': supported_langs
        }, status=400)
    
    if source_lang and source_lang not in supported_langs:
        return Response({
            'error': f"Unsupported source language: {source_lang}",
            'supported_languages': supported_langs
        }, status=400)
    
    try:
        # Import required modules
        import sys
        from transformers import M2M100ForConditionalGeneration
        
        # Add your custom path for small100 tokenizer
        SMALL100_PATH = "/home/anews/PS/translate/small100"  # Replace with your actual path
        if SMALL100_PATH not in sys.path:
            sys.path.append(SMALL100_PATH)
        
        from tokenization_small100 import SMALL100Tokenizer
        
        # Load model and tokenizer (consider caching these for better performance)
        # You might want to load these once at startup rather than per request
        model = M2M100ForConditionalGeneration.from_pretrained(SMALL100_PATH)
        tokenizer = SMALL100Tokenizer.from_pretrained(SMALL100_PATH)
        
        # Set target language
        tokenizer.tgt_lang = target_lang
        
        # If source language is provided, set it (optional)
        if source_lang:
            tokenizer.src_lang = source_lang
        
        # Tokenize and translate
        encoded_text = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        
        # Generate translation
        generated_tokens = model.generate(
            **encoded_text,
            max_length=512,
            num_beams=5,
            length_penalty=1.0,
            early_stopping=True
        )
        
        # Decode the translation
        translated_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        
        return Response({
            'original_text': text,
            'translated_text': translated_text,
            'source_lang': source_lang if source_lang else 'auto-detected',
            'target_lang': target_lang,
            'model_used': 'small100'
        })
        
    except ImportError as e:
        return Response({
            'error': f"Failed to import required modules: {str(e)}",
            'hint': "Make sure the small100 tokenizer path is correctly set"
        }, status=500)
        
    except Exception as e:
        return Response({
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
        'languages': languages,
        'total': len(languages)
    })