from django.urls import path
from . import views
from . import services

from AnalyticsModel.views import metrics_dashboard
from RateLimitModel.models import api_search_rate_limit, api_rate_limit





app_name = 'AnalyticsModel'

urlpatterns = [
    path('dashboard/', services.analytics_dashboard, name='dashboard'),
    path("metrics/", metrics_dashboard, name="metrics_dashboard"),
    path('api/<str:metric_type>/', api_search_rate_limit(services.AnalyticsAPIView.as_view()), name='api'),
    
    path("SystemCheckAPIView/", api_search_rate_limit(services.SystemCheckAPIView.as_view()), name="check-gpu"),
]