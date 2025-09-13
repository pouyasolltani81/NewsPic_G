from django.urls import path
from . import views
from django.views.decorators.clickjacking import xframe_options_exempt

from .services import DaemonManagerView, DaemonServiceView, DaemonServiceDetailView
from RateLimitModel.models import api_search_rate_limit, api_rate_limit


urlpatterns = [
    path('daemon/', xframe_options_exempt(DaemonManagerView.as_view()), name='daemon-manager'),
    path('api/daemons/', api_rate_limit(DaemonServiceView.as_view()), name='daemon-list'),
    path('api/daemons/<str:service_name>/<str:action>/', api_rate_limit(DaemonServiceDetailView.as_view()), name='daemon-action'),
    path('api/daemons/<str:service_name>/', api_rate_limit(DaemonServiceDetailView.as_view()), name='daemon-detail'),
]

urlpatterns += [
    path('', views.dashboard, name='dashboard'),
    path('Docs/', views.Docs_view, name='Docs'),
    
]


urlpatterns += [
    path('Dashboard/', views.Dashboard_view, name='Dashboard'),
]
