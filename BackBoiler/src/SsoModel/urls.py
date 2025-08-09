from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .services import CreateASP, ChangeASPActivation
from .services import ChangeUserActivation, GetUserAsps
from .services import GetAspCredential, GetASPUserbyUserId

urlpatterns = [
    path('CreateASP/', CreateASP, name='create_asp'),
    path('ChangeASPActivation/', ChangeASPActivation, name='change_asp_activation'),
    path('GetUserAsps/', GetUserAsps, name='get_user_asps'),

    path('ChangeUserActivation/', ChangeUserActivation, name='change_user_activation'),
    path('GetAspCredential/', GetAspCredential, name='get_asp_credential'),
    path('GetASPUserbyUserId/', GetASPUserbyUserId, name='get_asp_user_by_user_id'),
] 

urlpatterns = format_suffix_patterns(urlpatterns)