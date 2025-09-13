from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt




@xframe_options_exempt  

def ShowLogs(request):
    return render(request, 'logs.html')