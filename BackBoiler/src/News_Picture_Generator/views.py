from django.shortcuts import render
from django.conf import settings
from django.templatetags.static import static
from django.core.paginator import Paginator
import os, json

def NewsDashboard_view(request):
    # ===== USER CONTEXT =====
    context = {}
    if request.user.is_authenticated:
        context.update({
            'user_id': request.user.id,
            'username': request.user.username,
        })

    # ===== NEWS DATA =====
    BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
    json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
    crypto_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')
    custom_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'custom_images')

    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)

    # Reverse order (latest first)
    data = list(data_dict.values())[::-1]

    # Adjust filepaths & tag source type
    for item in data:
        filename = os.path.basename(item['filepath'])

        # Decide path based on original source
        if os.path.exists(os.path.join(custom_images_dir, filename)):
            item['filepath'] = f"/custom_images/{filename}"
            item['image_source'] = "custom"
        else:
            item['filepath'] = f"/crypto_news_images/{filename}"
            item['image_source'] = "crypto"

        # Add timestamp if not present
        item['timestamp'] = item.get('timestamp', None)

    # ===== FILTERING =====
    filter_type = request.GET.get('filter', 'all').lower()
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
                filtered_data.append(item)  # Implement timestamp comparison if needed
            elif filter_type == 'crypto_images' and item['image_source'] == 'crypto':
                filtered_data.append(item)
            elif filter_type == 'custom_images' and item['image_source'] == 'custom':
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
