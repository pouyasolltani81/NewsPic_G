from django.shortcuts import render
from django.conf import settings
from django.templatetags.static import static
from django.core.paginator import Paginator
import os, json

def NewsDashboard_view(request):
    BASE_EXTERNAL_PATH = '/home/anews/PS/gan'

    json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
    images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')

    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)  # dict of dicts

    # Convert dict values to list for easier template iteration
    data = list(data_dict.values())

    # Adjust filepaths for image serving
    for item in data:
        filename = os.path.basename(item['filepath'])
        item['filepath'] = f"/crypto_news_images/{filename}"

    # Pagination — show 9 items per page
    paginator = Paginator(data, 9)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'NewsDashboard/NewsDashboard.html', {
        'page_obj': page_obj,
    })
