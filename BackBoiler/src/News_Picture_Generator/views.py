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
        item['summaryEn'] = item.get('summaryEn', '')
        item['selected_scope'] = item.get('selected_scope', '')
        
        
        
        
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

