# views.py
from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import os, json
from datetime import datetime
import requests
from django.conf import settings
from django.utils import translation

def NewsDashboard_view(request):
    # ===== USER CONTEXT =====
    context = {}
    auth_token = None
    
    if request.user.is_authenticated:
        context.update({
            'user_id': request.user.id,
            'username': request.user.username,
        })
    
    # ===== LANGUAGE SETTINGS =====
    current_language = translation.get_language()
    if not current_language:
        current_language = settings.LANGUAGE_CODE
    target_lang = current_language.split('-')[0]
    
    # ===== PATHS =====
    BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
    json_path_gen = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
    json_path_custom = os.path.join(BASE_EXTERNAL_PATH, 'custom_pics.json')

    # ===== LOAD generated_history.json =====
    with open(json_path_gen, 'r', encoding='utf-8') as f:
        data_dict_gen = json.load(f)
    data_gen = list(data_dict_gen.values())

    # Fix generated items filepaths and timestamps (NO TRANSLATION YET)
    for idx, item in enumerate(data_gen):
        filename = os.path.basename(item.get('filepath', ''))
        item['filepath'] = f"/crypto_news_images/{filename}"
        item['item_id'] = f"gen_{idx}"  # Add unique ID for AJAX
        
        # Store original title
        item['original_title'] = item.get('title', '')
        
        # Normalize timestamp
        ts = item.get('timestamp')
        if ts:
            try:
                item['timestamp'] = datetime.fromisoformat(ts)
            except Exception:
                item['timestamp'] = None
        else:
            item['timestamp'] = None

    # ===== LOAD custom_pics.json =====
    with open(json_path_custom, 'r', encoding='utf-8') as f:
        data_custom_raw = json.load(f)

    if isinstance(data_custom_raw, dict):
        data_custom = data_custom_raw.get('generations', [])
    elif isinstance(data_custom_raw, list):
        data_custom = data_custom_raw
    else:
        data_custom = []

    # Fix custom items filepaths and timestamps (NO TRANSLATION YET)
    for idx, item in enumerate(data_custom):
        if not isinstance(item, dict):
            continue
        filename = os.path.basename(item.get('filepath', ''))
        item['filepath'] = f"/custom_images/{filename}"
        item['item_id'] = f"custom_{idx}"  # Add unique ID for AJAX
        
        # Store original title
        item['original_title'] = item.get('title', '')

        ts = item.get('timestamp')
        if ts:
            try:
                item['timestamp'] = datetime.fromisoformat(ts)
            except Exception:
                item['timestamp'] = None
        else:
            item['timestamp'] = None

    # ===== MERGE and SORT =====
    data = data_gen + data_custom
    data.sort(key=lambda x: x['timestamp'] or datetime.min, reverse=True)

    # ===== FILTERING =====
    filter_type = request.GET.get('filter', 'all')
    if filter_type != 'all':
        filtered_data = []
        for item in data:
            title_lower = item.get('original_title', '').lower()
            prompt_lower = item.get('prompt', '').lower()

            if filter_type == 'bitcoin' and ('bitcoin' in title_lower or 'bitcoin' in prompt_lower or 'btc' in title_lower):
                filtered_data.append(item)
            elif filter_type == 'ethereum' and ('ethereum' in title_lower or 'ethereum' in prompt_lower or 'eth' in title_lower):
                filtered_data.append(item)
            elif filter_type == 'defi' and ('defi' in title_lower or 'defi' in prompt_lower or 'decentralized' in title_lower):
                filtered_data.append(item)
            elif filter_type == 'recent':
                if item['timestamp'] and (datetime.now() - item['timestamp']).days <= 7:
                    filtered_data.append(item)
        data = filtered_data

    # ===== PAGINATION =====
    paginator = Paginator(data, 6)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ===== CONTEXT =====
    context['page_obj'] = page_obj
    context['current_filter'] = filter_type
    context['current_lang'] = target_lang
    context['needs_translation'] = target_lang != 'en'  # Flag for template

    return render(request, 'NewsDashboard/NewsDashboard.html', context)


@require_http_methods(["POST"])
def translate_batch(request):
    """AJAX endpoint for batch translation"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    items = json.loads(request.body).get('items', [])
    target_lang = json.loads(request.body).get('target_lang', 'en')
    
    translated_items = []
    
    for item in items:
        item_id = item.get('id')
        title = item.get('title', '')
        
        if title and target_lang != 'en':
            translated_title = translate_title(title, target_lang)
            translated_items.append({
                'id': item_id,
                'translated_title': translated_title
            })
        else:
            translated_items.append({
                'id': item_id,
                'translated_title': title
            })
    
    return JsonResponse({'translations': translated_items})

import sys
import logging

# Configure logging at the module level
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def translate_title(title, target_lang='en', auth_token=None):
    """Helper function to translate a title using the translation API"""
    if not title:
        return title
    
    try:
        translate_url = getattr(settings, 'TRANSLATE_API_URL', 'http://79.175.177.113:19800/Translate/translate/')
        
        # Force flush output
        print(f"\n=== TRANSLATION REQUEST ===", file=sys.stderr)
        print(f"URL: {translate_url}", file=sys.stderr)
        print(f"Title: {title}", file=sys.stderr)
        print(f"Target Lang: {target_lang}", file=sys.stderr)
        print(f"========================\n", file=sys.stderr)
        sys.stderr.flush()
        
        # Also use logger
        logger.info(f"Translating: '{title}' to '{target_lang}'")
        
        headers = {}
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        
        # Log the full request payload
        request_payload = {
            'text': title,
            'target_lang': target_lang,
            'source_lang': ''
        }
        print(f"Request Payload: {json.dumps(request_payload, indent=2)}", file=sys.stderr)
        
        response = requests.post(
            translate_url,
            json=request_payload,
            headers=headers,
            timeout=5
        )
        
        # Log the response
        print(f"\n=== TRANSLATION RESPONSE ===", file=sys.stderr)
        print(f"Status Code: {response.status_code}", file=sys.stderr)
        print(f"Response Headers: {dict(response.headers)}", file=sys.stderr)
        print(f"Response Content: {response.text}", file=sys.stderr)
        print(f"===========================\n", file=sys.stderr)
        sys.stderr.flush()
        
        if response.status_code == 200:
            result = response.json()
            print(f"Parsed JSON: {json.dumps(result, indent=2)}", file=sys.stderr)
            
            if result.get('success'):
                # Check the exact structure of the response
                if 'data' in result and isinstance(result['data'], dict):
                    translated_text = result['data'].get('translated_text', title)
                else:
                    # Maybe the structure is different?
                    translated_text = result.get('translated_text', title)
                
                print(f"Translation successful: '{title}' -> '{translated_text}'", file=sys.stderr)
                return translated_text
            else:
                print(f"Translation failed: success=False", file=sys.stderr)
        else:
            print(f"HTTP Error: {response.status_code}", file=sys.stderr)
        
        return title
        
    except requests.exceptions.Timeout:
        print(f"TIMEOUT ERROR: Request timed out", file=sys.stderr)
        return title
    except requests.exceptions.RequestException as e:
        print(f"REQUEST ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return title
    except Exception as e:
        print(f"GENERAL ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return title