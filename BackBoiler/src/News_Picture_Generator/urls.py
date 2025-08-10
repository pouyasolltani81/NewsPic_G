from django.urls import path
from . import views  # or wherever your views are

import os
from django.urls import path
from django.views.static import serve

app_dir = os.path.dirname(os.path.abspath(__file__))
images_dir = os.path.join(app_dir, 'crypto_news_images')

from . import services

from .services import (
    download_image_by_title,
    check_image_exists,
    list_generated_images,
    generate_custom_image,
    list_custom_images,
    download_custom_image,
    search_custom_images,
    custom_image_stats,
    delete_custom_image,
    news_image_stats,
    download_image_with_logo,
    preview_logo_placement
)

urlpatterns = [
    # Existing news image endpoints
    path('news-images/download/', download_image_by_title, name='download-news-image'),
    path('news-images/check/', check_image_exists, name='check-news-image'),
    path('news-images/list/', list_generated_images, name='list-news-images'),
    path('news-images/stats/', news_image_stats, name='news-image-stats'),
    
    
    # Custom image generation endpoints
    path('custom-images/generate/', generate_custom_image, name='generate-custom-image'),
    path('custom-images/list/', list_custom_images, name='list-custom-images'),
    path('custom-images/download/', download_custom_image, name='download-custom-image'),
    path('custom-images/search/', search_custom_images, name='search-custom-images'),
    path('custom-images/stats/', custom_image_stats, name='custom-image-stats'),
    # path('custom-images/delete/', delete_custom_image, name='delete-custom-image'),
    
    
    
    # LOGO 
    path('news-images/download-with-logo/', download_image_with_logo, name='download-news-image-with-logo'),
    # path('news-images/preview-logo/', preview_logo_placement, name='preview-logo-placement'),
]


urlpatterns += [
    path('NewsDashboard/', views.NewsDashboard_view, name='NewsDashboard'),
]
