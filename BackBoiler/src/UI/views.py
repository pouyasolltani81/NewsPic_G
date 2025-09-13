from django.shortcuts import render
# views.py
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from app.config_utils import config_manager
import json


        
def dashboard(request):
    config = config_manager.load_config()
    return render(request, "ui/index.html", {'config': config})

def Dashboard_view(request):
    config = config_manager.load_config()
    return render(request, 'Dashboard/Dashboard.html', {'config': config})



def Docs_view(request):
    config = config_manager.load_config()
    return render(request, 'Docs/Docs.html', {'config': config})
                
                