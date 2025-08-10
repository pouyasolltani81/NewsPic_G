from django.urls import path
from . import views  # or wherever your views are

import os
from django.urls import path
from django.views.static import serve

app_dir = os.path.dirname(os.path.abspath(__file__))
images_dir = os.path.join(app_dir, 'crypto_news_images')

from . import services


urlpatterns = [
    path('download-image/', services.download_image_by_title, name='download_image_by_title'),
    path('check-image/', services.check_image_exists, name='check_image_exists'),
    path('list-images/', services.list_generated_images, name='list_generated_images'),
]

urlpatterns += [
    path('NewsDashboard/', views.NewsDashboard_view, name='NewsDashboard'),
]
