# AnalyticsModel/views.py
from django.shortcuts import render
from .models import SystemMetrics
from django.core.paginator import Paginator
from django.views.decorators.clickjacking import xframe_options_exempt




  


@xframe_options_exempt
def metrics_dashboard(request):
    metrics_list = SystemMetrics.objects.order_by('-timestamp')
    paginator = Paginator(metrics_list, 15)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "metrics_dashboard.html", {
        "page_obj": page_obj,
        "metrics": metrics_list,  
    })
    
