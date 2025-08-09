from django.shortcuts import render
from .forms import DateForm
from datetime import date

def ShowLogs(request):
    return render(request, 'logs.html')


def Dashboard(request):
    
    if request.user.is_authenticated:
        user_id = request.user.id
        username = request.user.username
        # You can also access other user attributes like email, first_name, last_name
        # user_email = request.user.email 
        # user_first_name = request.user.first_name

        context = {
            'user_id': user_id,
            'username': username,
        }
        return render(request, "dashboard/dashboard.html" , context)
    else:
        # Handle cases where the user is not authenticated
        return render(request, "dashboard/dashboard.html" )


