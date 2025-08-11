from django.urls import path
from django.views.static import serve
import os
from . import services

app_dir = os.path.dirname(os.path.abspath(__file__))
images_dir = os.path.join(app_dir, 'crypto_news_images')


from .services import (
    translate_text,
    list_supported_languages
)

urlpatterns = [
    # Existing news image endpoints
    path('trnaslate/normal/', translate_text, name='translate_text'),
    path('trnaslate/list_of_langs/', list_supported_languages, name='list_supported_languages'),
    
]

