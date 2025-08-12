from django.shortcuts import render
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

    # ===== PATHS =====
    BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
    json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
    crypto_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')
    custom_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'custom_images')

    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)

    # Reverse order (latest first)
    data = list(data_dict.values())[::-1]

    combined_data = []

    # Add crypto image entries
    for item in data:
        filename = os.path.basename(item['filepath'])
        crypto_path = os.path.join(crypto_images_dir, filename)
        if os.path.exists(crypto_path):
            new_item = dict(item)
            new_item['filepath'] = f"/crypto_news_images/{filename}"
            new_item['image_source'] = "crypto"
            new_item['timestamp'] = new_item.get('timestamp', None)
            combined_data.append(new_item)

    # Add custom image entries
    for item in data:
        filename = os.path.basename(item['filepath'])
        custom_path = os.path.join(custom_images_dir, filename)
        if os.path.exists(custom_path):
            new_item = dict(item)
            new_item['filepath'] = f"/custom_images/{filename}"
            new_item['image_source'] = "custom"
            new_item['timestamp'] = new_item.get('timestamp', None)
            combined_data.append(new_item)

    # ===== FILTERING =====
    filter_type = request.GET.get('filter', 'all').lower()
    if filter_type != 'all':
        combined_data = [
            item for item in combined_data
            if (
                (filter_type == 'bitcoin' and ('bitcoin' in item.get('title', '').lower() or 'btc' in item.get('title', '').lower() or 'bitcoin' in item.get('prompt', '').lower()))
                or (filter_type == 'ethereum' and ('ethereum' in item.get('title', '').lower() or 'eth' in item.get('title', '').lower() or 'ethereum' in item.get('prompt', '').lower()))
                or (filter_type == 'defi' and ('defi' in item.get('title', '').lower() or 'decentralized' in item.get('prompt', '').lower()))
                or (filter_type == 'recent')  # Add real date filtering here if needed
                or (filter_type == 'crypto_images' and item['image_source'] == 'crypto')
                or (filter_type == 'custom_images' and item['image_source'] == 'custom')
            )
        ]

    # ===== PAGINATION =====
    paginator = Paginator(combined_data, 6)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ===== CONTEXT =====
    context['page_obj'] = page_obj
    context['current_filter'] = filter_type

    return render(request, 'NewsDashboard/NewsDashboard.html', context)
