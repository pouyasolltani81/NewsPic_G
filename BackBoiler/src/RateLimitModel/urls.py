from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .services import GetRateLimitList, GetBlacklist, GetWhitelist

urlpatterns = [
    path('GetRateLimitList/', GetRateLimitList, name='get_rate_limit_list'),
    path('GetBlacklist/', GetBlacklist, name='get_blacklist'),
    path('GetWhitelist/', GetWhitelist, name='get_whitelist'),
]

urlpatterns = format_suffix_patterns(urlpatterns)
