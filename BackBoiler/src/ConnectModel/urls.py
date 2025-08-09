from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .services import CreateConnection, GetConnections, GetCredential, ChangeConnectionActivation, RequestToExec

urlpatterns = [
    path('CreateConnection/', CreateConnection, name='create_connection'),
    path('GetConnections/', GetConnections, name='get_connections'),
    path('GetCredential/', GetCredential, name='get_credential'),
    path('ChangeConnectionStatus/', ChangeConnectionActivation, name='change_connection_status'),
    path('RequestToExec/', RequestToExec, name='request_to_exec'),
] 

urlpatterns = format_suffix_patterns(urlpatterns)