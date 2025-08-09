from django.urls import path
from . import views  # or wherever your views are

import os
from django.urls import path
from django.views.static import serve

app_dir = os.path.dirname(os.path.abspath(__file__))
images_dir = os.path.join(app_dir, 'crypto_news_images')

urlpatterns = [
   
    # path('crypto_news_images/<path:path>/', serve, {'document_root': images_dir}, name='crypto_images'),
]


urlpatterns += [
    path('NewsDashboard/', views.NewsDashboard_view, name='NewsDashboard'),
]
