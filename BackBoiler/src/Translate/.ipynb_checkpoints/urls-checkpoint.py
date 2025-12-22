from django.urls import path
from . import services

app_name = 'translate'

urlpatterns = [
    # Translation endpoints
    path('translate/', services.translate, name='translate'),
    path('translate/batch/', services.translate_batch, name='translate_batch'),
    
    # Async translation endpoints
    path('translate/async/', services.translate_async, name='translate_async'),
    path('translate/async/<str:uuid>/', services.get_async_translation, name='get_async_translation'),
    path('translate/async/<str:uuid>/delete/', services.delete_async_translation, name='delete_async_translation'),
    path('translate/async-list/', services.list_async_translations, name='list_async_translations'),
    
    # Batch async translation endpoints
    path('translate/batch/async/', services.translate_batch_async, name='translate_batch_async'),

    
    # Language endpoints
    path('languages/', services.get_supported_languages, name='get_supported_languages'),
    
    # Configuration endpoints
    path('config/', services.get_config, name='get_config'),
    path('config/update/', services.update_config, name='update_config'),
    path('config/memory/', services.update_memory_config, name='update_memory_config'),
    path('config/glossary/', services.update_glossary, name='update_glossary'),
    path('config/glossary/delete/', services.delete_glossary, name='delete_glossary'),
    path('config/generation/', services.update_generation_params, name='update_generation_params'),
    
    # Model management endpoints
    path('memory/', services.get_memory_usage, name='get_memory_usage'),
    path('reload/', services.reload_model, name='reload_model'),
    path('free-memory/', services.free_gpu_memory, name='free_gpu_memory'),
    
    # Health check
    path('health/', services.health_check, name='health_check'),
]