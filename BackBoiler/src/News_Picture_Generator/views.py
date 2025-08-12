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
            # Optional extra fields:
            # 'user_email': request.user.email,
            # 'first_name': request.user.first_name,
            # 'last_name': request.user.last_name,
        })

    # ===== NEWS DATA =====
    BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
    json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
    images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')

    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)

    # Reverse order (latest first)
    data = list(data_dict.values())[::-1]

    # Adjust image filepaths
    for item in data:
        filename = os.path.basename(item['filepath'])
        item['filepath'] = f"/crypto_news_images/{filename}"

    # Pagination (6 items per page)
    paginator = Paginator(data, 6)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Add pagination to context
    context['page_obj'] = page_obj

    return render(request, 'NewsDashboard/NewsDashboard.html', context)
