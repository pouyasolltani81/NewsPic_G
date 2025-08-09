from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .services import GetUserToken, GetUserbyUUID

urlpatterns = [
    path('GetUserToken/', GetUserToken, name='get_user_token'),
    path('GetUserbyUUID/', GetUserbyUUID, name='get_user_by_uuid'),
] 

urlpatterns = format_suffix_patterns(urlpatterns)