# core/management/commands/startcustomapp.py
import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Creates a new Django app with boilerplate files and auto-configuration'

    def add_arguments(self, parser):
        parser.add_argument('app_name', type=str)

    def handle(self, *args, **options):
        app_name = options['app_name']

        # Step 1: Call the built-in startapp
        self.stdout.write(f"📦 Creating app '{app_name}'...")
        call_command('startapp', app_name)

        # Step 2: Add your custom commands
        app_path = os.path.join(os.getcwd(), app_name)

        # Create templates/app_name folder
        templates_path = os.path.join(app_path, 'templates', app_name)
        os.makedirs(templates_path, exist_ok=True)

        # Create static/app_name folder
        static_path = os.path.join(app_path, 'static', app_name)
        os.makedirs(static_path, exist_ok=True)

        # Create urls.py file with imports
        urls_path = os.path.join(app_path, 'urls.py')
        if not os.path.exists(urls_path):
            with open(urls_path, 'w') as f:
                f.write(
f"""from django.urls import path
from . import views
from . import services

app_name = '{app_name}'

urlpatterns = [
    # path('', views.index, name='index'),
    # path('list/', views.list_view, name='list'),
    # path('create/', views.create_view, name='create'),
    # path('<int:pk>/', views.detail_view, name='detail'),
    # path('<int:pk>/update/', views.update_view, name='update'),
    # path('<int:pk>/delete/', views.delete_view, name='delete'),
]
""")

        # Create services.py file
        services_path = os.path.join(app_path, 'services.py')
        if not os.path.exists(services_path):
            with open(services_path, 'w') as f:
                f.write(
f"""\"\"\"
Business logic and service functions for {app_name} app.
\"\"\"
from django.db import transaction
from django.core.exceptions import ValidationError


class {app_name.capitalize()}Service:
    \"\"\"
    Service class for {app_name} related operations.
    \"\"\"
    
    @staticmethod
    def example_service_method():
        \"\"\"
        Example service method.
        \"\"\"
        pass


# Example service functions
def process_{app_name}_data(data):
    \"\"\"
    Process {app_name} data.
    
    Args:
        data: Input data to process
        
    Returns:
        Processed data
    \"\"\"
    # Add your business logic here
    return data


@transaction.atomic
def create_{app_name}_with_validation(data):
    \"\"\"
    Create {app_name} with validation.
    
    Args:
        data: Dictionary containing {app_name} data
        
    Returns:
        Created {app_name} instance
        
    Raises:
        ValidationError: If validation fails
    \"\"\"
    # Add your validation and creation logic here
    pass
""")

        # Step 3: Add app to INSTALLED_APPS in settings.py
        self.add_to_installed_apps(app_name)

        # Step 4: Add URL pattern to main urls.py
        self.add_to_main_urls(app_name)

        # Create a basic view in views.py
        self.update_views_file(app_path, app_name)

        self.stdout.write(self.style.SUCCESS(f"✅ App '{app_name}' created successfully!"))
        self.stdout.write(self.style.SUCCESS(f"   - Added to INSTALLED_APPS"))
        self.stdout.write(self.style.SUCCESS(f"   - Added to main urls.py"))
        self.stdout.write(self.style.SUCCESS(f"   - Created services.py"))
        self.stdout.write(self.style.SUCCESS(f"   - Created urls.py with imports"))
        self.stdout.write(self.style.SUCCESS(f"   - Created templates/{app_name}/ directory"))
        self.stdout.write(self.style.SUCCESS(f"   - Created static/{app_name}/ directory"))

    def add_to_installed_apps(self, app_name):
        """Add the app to INSTALLED_APPS in settings.py"""
        settings_path = os.path.join(settings.BASE_DIR, 'app', 'settings.py')
        
        with open(settings_path, 'r') as f:
            content = f.read()

        # Check if app already exists
        if f"'{app_name}'" in content or f'"{app_name}"' in content:
            self.stdout.write(self.style.WARNING(f"App '{app_name}' already in INSTALLED_APPS"))
            return

        # Find INSTALLED_APPS and add the new app
        pattern = r'(INSTALLED_APPS\s*=\s*```math)(.*?)(```)'
        
        def replacer(match):
            before = match.group(1)
            apps = match.group(2)
            after = match.group(3)
            
            # Add the new app before the closing bracket
            # Check if there's already a trailing comma
            apps_stripped = apps.rstrip()
            if apps_stripped and not apps_stripped.endswith(','):
                apps_stripped += ','
            
            new_apps = apps_stripped + f"\n    '{app_name}',"
            
            return before + new_apps + '\n' + after

        new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
        
        with open(settings_path, 'w') as f:
            f.write(new_content)

    def add_to_main_urls(self, app_name):
        """Add URL pattern to main urls.py"""
        urls_path = os.path.join(settings.BASE_DIR, 'app', 'urls.py')
        
        with open(urls_path, 'r') as f:
            content = f.read()

        # Check if the app URL already exists
        if f"{app_name}.urls" in content:
            self.stdout.write(self.style.WARNING(f"URL pattern for '{app_name}' already exists"))
            return

        # Add import if include is not already imported
        if 'from django.urls import' in content and 'include' not in content:
            content = content.replace(
                'from django.urls import path',
                'from django.urls import path, include'
            )
        elif 'from django.urls import' not in content:
            # Add the import at the top after django imports
            import_line = "from django.urls import path, include\n"
            content = import_line + content

        # Find urlpatterns and add the new URL
        pattern = r'(urlpatterns\s*=\s*```math)(.*?)(```)'
        
        def replacer(match):
            before = match.group(1)
            patterns = match.group(2)
            after = match.group(3)
            
            # Add the new URL pattern
            patterns_stripped = patterns.rstrip()
            if patterns_stripped and not patterns_stripped.endswith(','):
                patterns_stripped += ','
            
            new_pattern = patterns_stripped + f"\n    path('{app_name}/', include('{app_name}.urls')),"
            
            return before + new_pattern + '\n' + after

        new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
        
        with open(urls_path, 'w') as f:
            f.write(new_content)

    def update_views_file(self, app_path, app_name):
        """Update views.py with basic view examples"""
        views_path = os.path.join(app_path, 'views.py')
        
        with open(views_path, 'w') as f:
            f.write(
f"""from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from . import services


def index(request):
    \"\"\"
    Index view for {app_name}.
    \"\"\"
    context = {{
        'title': '{app_name.capitalize()} Home',
    }}
    return render(request, '{app_name}/index.html', context)


# Example: Function-based views
def list_view(request):
    \"\"\"
    List view for {app_name}.
    \"\"\"
    # items = Model.objects.all()
    context = {{
        'title': '{app_name.capitalize()} List',
        # 'items': items,
    }}
    return render(request, '{app_name}/list.html', context)


def detail_view(request, pk):
    \"\"\"
    Detail view for {app_name}.
    \"\"\"
    # item = get_object_or_404(Model, pk=pk)
    context = {{
        'title': '{app_name.capitalize()} Detail',
        # 'item': item,
    }}
    return render(request, '{app_name}/detail.html', context)


# Example: Class-based views (commented out)
# class {app_name.capitalize()}ListView(ListView):
#     model = {app_name.capitalize()}Model
#     template_name = '{app_name}/list.html'
#     context_object_name = 'items'
#     paginate_by = 10


# class {app_name.capitalize()}CreateView(CreateView):
#     model = {app_name.capitalize()}Model
#     template_name = '{app_name}/form.html'
#     fields = '__all__'
#     success_url = reverse_lazy('{app_name}:list')
""")

        # Create a basic index.html template
        index_template_path = os.path.join(app_path, 'templates', app_name, 'index.html')
        with open(index_template_path, 'w') as f:
            f.write(
f"""{{% extends 'base.html' %}}

{{% block title %}}{app_name.capitalize()} Home{{% endblock %}}

{{% block content %}}
<div class="container">
    <h1>Welcome to {app_name.capitalize()}</h1>
    <p>This is the index page for the {app_name} app.</p>
</div>
{{% endblock %}}
""")