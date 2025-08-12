# from django.shortcuts import render
# from django.conf import settings
# from django.templatetags.static import static
# from django.core.paginator import Paginator
# import os, json


# def NewsDashboard_view(request):
#     # ===== USER CONTEXT =====
#     context = {}
#     if request.user.is_authenticated:
#         context.update({
#             'user_id': request.user.id,
#             'username': request.user.username,
#         })

#     # ===== NEWS DATA =====
#     BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
#     json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
#     images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')

#     with open(json_path, 'r', encoding='utf-8') as f:
#         data_dict = json.load(f)

#     # Reverse order (latest first)
#     data = list(data_dict.values())[::-1]

#     # Adjust image filepaths and add metadata for filtering
#     for item in data:
#         filename = os.path.basename(item['filepath'])
#         item['filepath'] = f"/crypto_news_images/{filename}"
        
#         # Add timestamp if available for "recent" filter
#         if 'timestamp' in item:
#             item['timestamp'] = item['timestamp']
#         else:
#             # You might want to extract this from the filename or add it to your JSON
#             item['timestamp'] = None

#     # Apply filter if provided
#     filter_type = request.GET.get('filter', 'all')
#     if filter_type != 'all':
#         filtered_data = []
#         for item in data:
#             title_lower = item.get('title', '').lower()
#             prompt_lower = item.get('prompt', '').lower()
            
#             if filter_type == 'bitcoin' and ('bitcoin' in title_lower or 'bitcoin' in prompt_lower or 'btc' in title_lower):
#                 filtered_data.append(item)
#             elif filter_type == 'ethereum' and ('ethereum' in title_lower or 'ethereum' in prompt_lower or 'eth' in title_lower):
#                 filtered_data.append(item)
#             elif filter_type == 'defi' and ('defi' in title_lower or 'defi' in prompt_lower or 'decentralized' in title_lower):
#                 filtered_data.append(item)
#             elif filter_type == 'recent':
#                 # Implement recent logic based on timestamp
#                 filtered_data.append(item)
        
#         data = filtered_data

#     # Pagination (6 items per page)
#     paginator = Paginator(data, 6)
#     page_number = request.GET.get('page', 1)
#     page_obj = paginator.get_page(page_number)

#     # Add pagination and filter to context
#     context['page_obj'] = page_obj
#     context['current_filter'] = filter_type

#     return render(request, 'NewsDashboard/NewsDashboard.html', context)


# from django.shortcuts import render
# from django.core.paginator import Paginator
# import os, json

# def NewsDashboard_view(request):
#     context = {}

#     # ===== USER CONTEXT =====
#     if request.user.is_authenticated:
#         context.update({
#             'user_id': request.user.id,
#             'username': request.user.username,
#         })

#     # ===== PATHS =====
#     BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
#     json_path = os.path.join(BASE_EXTERNAL_PATH, 'custom_pics.json')  # or generated_history.json
#     images_dir = os.path.join(BASE_EXTERNAL_PATH, 'custom_images')

#     # ===== LOAD JSON SAFELY =====
#     with open(json_path, 'r', encoding='utf-8') as f:
#         loaded_data = json.load(f)
        
#     data = loaded_data.get('generations', [])
#     if not isinstance(data, list):
#         data = []
#     data = data[::-1]

#     # ===== PROCESS DATA =====
#     processed_data = []
#     for item in data:
#         if not isinstance(item, dict):
#             continue  # skip invalid entries

#         filename = os.path.basename(item.get('filepath', ''))
#         item['filepath'] = f"/custom_images/{filename}"

#         item['timestamp'] = item.get('timestamp', None)
#         processed_data.append(item)

#     # ===== FILTER =====
#     filter_type = request.GET.get('filter', 'all')
#     if filter_type != 'all':
#         filtered_data = []
#         for item in processed_data:
#             title_lower = item.get('title', '').lower()
#             prompt_lower = item.get('prompt', '').lower()

#             if filter_type == 'bitcoin' and ('bitcoin' in title_lower or 'bitcoin' in prompt_lower or 'btc' in title_lower):
#                 filtered_data.append(item)
#             elif filter_type == 'ethereum' and ('ethereum' in title_lower or 'ethereum' in prompt_lower or 'eth' in title_lower):
#                 filtered_data.append(item)
#             elif filter_type == 'defi' and ('defi' in title_lower or 'defi' in prompt_lower or 'decentralized' in title_lower):
#                 filtered_data.append(item)
#             elif filter_type == 'recent':
#                 filtered_data.append(item)  # TODO: implement real timestamp check

#         processed_data = filtered_data

#     # ===== PAGINATION =====
#     paginator = Paginator(processed_data, 6)
#     page_number = request.GET.get('page', 1)
#     page_obj = paginator.get_page(page_number)

#     context['page_obj'] = page_obj
#     context['current_filter'] = filter_type

#     return render(request, 'NewsDashboard/NewsDashboard.html', context)



from django.shortcuts import render
from django.core.paginator import Paginator
import os, json
from datetime import datetime

def NewsDashboard_view(request):
    # ===== USER CONTEXT =====
    context = {}
    if request.user.is_authenticated:
        context.update({
            'user_id': request.user.id,
            'username': request.user.username,
        })

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

    # Fix generated items filepaths and timestamps
    for item in data_gen:
        filename = os.path.basename(item.get('filepath', ''))
        item['filepath'] = f"/crypto_news_images/{filename}"

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

    # Fix custom items filepaths and timestamps
    for item in data_custom:
        if not isinstance(item, dict):
            continue
        filename = os.path.basename(item.get('filepath', ''))
        item['filepath'] = f"/custom_images/{filename}"

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
            title_lower = item.get('title', '').lower()
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

    return render(request, 'NewsDashboard/NewsDashboard.html', context)
