from django.urls import path
from . import views

app_name = 'translate'

urlpatterns = [
    # Translation endpoints
    path('translate/', views.translate, name='translate'),
    path('translate/batch/', views.translate_batch, name='translate_batch'),
    path('languages/', views.get_supported_languages, name='get_supported_languages'),
    
    # Configuration endpoints
    path('config/', views.get_config, name='get_config'),
    path('config/update/', views.update_config, name='update_config'),
    path('config/memory/', views.update_memory_config, name='update_memory_config'),
    path('config/glossary/', views.update_glossary, name='update_glossary'),
    path('config/glossary/delete/', views.delete_glossary, name='delete_glossary'),
    path('config/generation/', views.update_generation_params, name='update_generation_params'),
    
    # Model management endpoints
    path('memory/', views.get_memory_usage, name='get_memory_usage'),
    path('reload/', views.reload_model, name='reload_model'),
    path('free-memory/', views.free_gpu_memory, name='free_gpu_memory'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
]