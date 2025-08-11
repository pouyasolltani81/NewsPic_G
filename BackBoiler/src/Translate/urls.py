from django.urls import path
from django.views.static import serve
import os
from . import services


app_name = 'translator'

from .services import (
    translate_text,
    list_supported_languages
)

urlpatterns = [
    path('translate/', translate_text, name='translate-text'),
    path('translate/languages/', list_supported_languages, name='list-languages'),
]