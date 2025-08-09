# core/management/commands/startcustomapp.py
import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Creates a new Django app and adds boilerplate files'

    def add_arguments(self, parser):
        parser.add_argument('app_name', type=str)

    def handle(self, *args, **options):
        app_name = options['app_name']

        # Step 1: Call the built-in startapp
        self.stdout.write(f"📦 Creating app '{app_name}'...")
        call_command('startapp', app_name)

        # Step 2: Add your custom commands
        app_path = os.path.join(os.getcwd(), app_name)

        # Example: Create templates/app_name folder
        templates_path = os.path.join(app_path, 'templates', app_name)
        os.makedirs(templates_path, exist_ok=True)

        # Example: Create a urls.py file
        urls_path = os.path.join(app_path, 'urls.py')
        if not os.path.exists(urls_path):
            with open(urls_path, 'w') as f:
                f.write(
f"""from django.urls import path

urlpatterns = [
    # path('', views.index, name='{app_name}_index'),
]
""")

        self.stdout.write(self.style.SUCCESS(f"✅ App '{app_name}' created with extras!"))
