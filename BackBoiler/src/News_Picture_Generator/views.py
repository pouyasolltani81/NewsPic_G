from django.shortcuts import render
import json
from django.conf import settings
from django.templatetags.static import static
import os
# Create your views here.


def NewsDashboard_view(request):
    app_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(app_dir, 'generated_history.json')
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)  # dict of dicts
    
    # Convert dict values to list for easier template iteration
    data = list(data_dict.values())
    
    # Adjust filepaths for image serving as discussed before:
    for item in data:
        filename = os.path.basename(item['filepath'])
        item['filepath'] = f"/crypto_news_images/{filename}"
    
    return render(request, 'NewsDashboard/NewsDashboard.html', {
        'news_items': data,
    })
