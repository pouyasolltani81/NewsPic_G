from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .services import GetUserToken, GetUserbyUUID, RegisterUser , LoginUser , LogoutUser , CheckAuthStatus , ChangePassword , get_all_user_ids, GetTelegramInfo, GetUserTelegramId

urlpatterns = [
    path('GetUserToken/', GetUserToken, name='get_user_token'),
    path('GetUserbyUUID/', GetUserbyUUID, name='get_user_by_uuid'),
    path('RegisterUser/', RegisterUser, name='register_user'),
    
    path('LoginUser/', LoginUser, name='login_user'),
   
    path('LogoutUser/', LogoutUser, name='logout_user'),
    path('CheckAuthStatus/', CheckAuthStatus, name='CheckAuthStatus'),
    path('ChangePassword/', ChangePassword, name='ChangePassword'),
    
    path('get-user-ids/', get_all_user_ids, name='get_user_ids'),

    path('GetTelegramInfo/', GetTelegramInfo, name='GetTelegramInfo'),
    path('GetUserTelegramId/', GetUserTelegramId, name='get_user_telegram_id'),
    
] 

urlpatterns = format_suffix_patterns(urlpatterns)