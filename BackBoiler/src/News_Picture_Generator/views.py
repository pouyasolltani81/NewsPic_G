from django.shortcuts import render
from django.core.paginator import Paginator
import os, json
from datetime import datetime
import requests
from django.conf import settings

def translate_title(title, target_lang='en', auth_token=None):
    """Helper function to translate a title using the translation API"""
    if not title:
        return title
    
    # Skip translation if already in target language or if translation fails
    try:
        # Get the translation API URL from settings or hardcode it
        translate_url = getattr(settings, 'TRANSLATE_API_URL', 'http://79.175.177.113:19800/Translate/translate/')
        
        headers = {}
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        
        response = requests.post(
            translate_url,
            json={
                'text': title,
                'target_lang': target_lang,
                'source_lang': ''  # auto-detect
            },
            headers=headers,
            timeout=5  # 5 second timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return result.get('data', {}).get('translated_text', title)
        
        return title  # Return original if translation fails
        
    except Exception as e:
        print(f"Translation error: {e}")
        return title  # Return original if translation fails

def NewsDashboard_view(request):
    # ===== USER CONTEXT =====
    context = {}
    auth_token = None
    
    if request.user.is_authenticated:
        context.update({
            'user_id': request.user.id,
            'username': request.user.username,
        })
        # Get auth token if you're using token authentication
        # auth_token = request.user.auth_token.key if hasattr(request.user, 'auth_token') else None

    # ===== LANGUAGE SETTINGS =====
    # Get target language from request or user preferences
    target_lang = 'fa'    # Or get from user preferences: target_lang = request.user.preferred_language if hasattr(request.user, 'preferred_language') else 'en'
    
    # ===== PATHS =====
    BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
    json_path_gen = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
    json_path_custom = os.path.join(BASE_EXTERNAL_PATH, 'custom_pics.json')

    images_dir_gen = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')
    images_dir_custom = os.path.join(BASE_EXTERNAL_PATH, 'custom_images')

    # ===== LOAD generated_history.json (dict expected) =====
    with open(json_path_gen, 'r', encoding='utf-8') as f:
        data_dict_gen = json.load(f)
    # Convert dict values to list and reverse for latest first
    data_gen = list(data_dict_gen.values())

    # Fix generated items filepaths and timestamps AND translate titles
    for item in data_gen:
        filename = os.path.basename(item.get('filepath', ''))
        item['filepath'] = f"/crypto_news_images/{filename}"
        
        # Translate title
        original_title = item.get('title', '')
        if original_title and target_lang != 'en':  # Assuming original titles are in English
            item['original_title'] = original_title
            item['title'] = translate_title(original_title, target_lang, auth_token)

        # Normalize timestamp (keep as datetime object or None)
        ts = item.get('timestamp')
        if ts:
            try:
                # Try parsing timestamp string into datetime (adjust format as needed)
                item['timestamp'] = datetime.fromisoformat(ts)
            except Exception:
                item['timestamp'] = None
        else:
            item['timestamp'] = None

    # ===== LOAD custom_pics.json (list expected under 'generations' key or directly a list) =====
    with open(json_path_custom, 'r', encoding='utf-8') as f:
        data_custom_raw = json.load(f)

    # Extract list depending on format
    if isinstance(data_custom_raw, dict):
        # If dict with 'generations' key, extract list
        data_custom = data_custom_raw.get('generations', [])
    elif isinstance(data_custom_raw, list):
        data_custom = data_custom_raw
    else:
        data_custom = []

    # Fix custom items filepaths and timestamps AND translate titles
    for item in data_custom:
        if not isinstance(item, dict):
            continue
        filename = os.path.basename(item.get('filepath', ''))
        item['filepath'] = f"/custom_images/{filename}"
        
        # Translate title
        original_title = item.get('title', '')
        if original_title and target_lang != 'en':
            item['original_title'] = original_title
            item['title'] = translate_title(original_title, target_lang, auth_token)

        ts = item.get('timestamp')
        if ts:
            try:
                item['timestamp'] = datetime.fromisoformat(ts)
            except Exception:
                item['timestamp'] = None
        else:
            item['timestamp'] = None

    # ===== MERGE the two datasets =====
    data = data_gen + data_custom

    # ===== SORT by timestamp descending (latest first) =====
    # Items without timestamp will be last
    data.sort(key=lambda x: x['timestamp'] or datetime.min, reverse=True)

    # ===== FILTERING =====
    filter_type = request.GET.get('filter', 'all')
    if filter_type != 'all':
        filtered_data = []
        for item in data:
            # Use original title for filtering if available (to ensure consistent filtering)
            title_lower = item.get('original_title', item.get('title', '')).lower()
            prompt_lower = item.get('prompt', '').lower()

            if filter_type == 'bitcoin' and ('bitcoin' in title_lower or 'bitcoin' in prompt_lower or 'btc' in title_lower):
                filtered_data.append(item)
            elif filter_type == 'ethereum' and ('ethereum' in title_lower or 'ethereum' in prompt_lower or 'eth' in title_lower):
                filtered_data.append(item)
            elif filter_type == 'defi' and ('defi' in title_lower or 'defi' in prompt_lower or 'decentralized' in title_lower):
                filtered_data.append(item)
            elif filter_type == 'recent':
                # For 'recent' filter, let's show items with timestamp within last 7 days
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

    return render(request, 'NewsDashboard/NewsDashboard.html', context)