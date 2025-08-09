from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .services import CheckUserAuth

urlpatterns = [
    path('CheckUserAuth/', CheckUserAuth, name='check_user_auth'),
] 

urlpatterns = format_suffix_patterns(urlpatterns)