from django.contrib import admin
from django.urls import path
from django.urls import re_path
from django.urls import include

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.conf.urls.i18n import i18n_patterns
import os
from django.views.static import serve

from django.conf import settings
from django.conf.urls.static import static

BASE_EXTERNAL_PATH = '/home/anews/PS/gan'

json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')
custom_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'custom_images')



urlpatterns = [

    path('swagger-yaml/', SpectacularAPIView.as_view(), name='swagger-yaml'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='swagger-yaml'), name='swagger'),
    path("__reload__/", include("django_browser_reload.urls")),

    path('admin/', admin.site.urls),
    path('RateLimit/', include('RateLimitModel.urls')),
    path('User/', include('UserModel.urls')),
    path('Auth/', include('AuthModel.urls')),
    path('Log/', include('LogModel.urls')),
    path('Connect/', include('ConnectModel.urls')),
    path('Sso/', include('SsoModel.urls')),
    path('News_Picture_Generator/', include('News_Picture_Generator.urls')),  
    path('Translate/', include('Translate.urls')),  
    
    
    
    
    path('', include('ui.urls')),  
    path('crypto_news_images/<path:path>/', serve, {'document_root': images_dir}),
    path('custom_images/<path:path>/', serve, {'document_root': custom_images_dir}),
    
   
    path('i18n/', include('django.conf.urls.i18n')),
    
    
    re_path(r'^static/(?P<path>.*)$', serve, {
        'document_root': '/home/anews/NewsPic_G/BackBoiler/src/static',
    }),  
    
] + static('/static/', document_root='/home/anews/NewsPic_G/BackBoiler/src/static')


# if settings.DEBUG:
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


