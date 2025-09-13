from django import template
from django.apps import apps
from django.urls import get_resolver, URLPattern, URLResolver
from django.template.loader import get_template
from django.template import TemplateDoesNotExist
import os
from pathlib import Path

register = template.Library()

@register.simple_tag
def discover_apps_and_services():
    """Discover all apps, their URLs, and templates"""
    discovered_apps = []
    
    for app_config in apps.get_app_configs():
        # Skip Django's built-in apps
        if app_config.name.startswith('django.'):
            continue
            
        app_data = {
            'name': app_config.name,
            'verbose_name': app_config.verbose_name,
            'services': [],
            'templates': []
        }
        
        # Discover URLs for this app
        app_urls = discover_app_urls(app_config.name)
        
        # Group URLs by view name or pattern
        services = {}
        for url_data in app_urls:
            view_name = url_data['view_name'] or url_data['pattern']
            if view_name not in services:
                services[view_name] = {
                    'name': view_name.replace('_', ' ').title(),
                    'urls': [],
                    'templates': []
                }
            services[view_name]['urls'].append(url_data)
        
        # Discover templates for this app
        app_templates = discover_app_templates(app_config.path)
        
        # Try to match templates with services
        for template_path in app_templates:
            template_name = os.path.basename(template_path)
            matched = False
            
            for service_name, service_data in services.items():
                # Simple matching: if template name contains service name
                if service_name.lower() in template_name.lower() or \
                   template_name.lower() in service_name.lower():
                    service_data['templates'].append({
                        'name': template_name,
                        'path': template_path
                    })
                    matched = True
                    break
            
            # If no match, add to app-level templates
            if not matched:
                app_data['templates'].append({
                    'name': template_name,
                    'path': template_path
                })
        
        app_data['services'] = list(services.values())
        discovered_apps.append(app_data)
    
    return discovered_apps

def discover_app_urls(app_name):
    """Discover all URLs for a specific app"""
    urls = []
    resolver = get_resolver()
    
    def extract_urls(url_patterns, prefix=''):
        for pattern in url_patterns:
            if isinstance(pattern, URLPattern):
                # Check if this URL belongs to our app
                if hasattr(pattern.callback, '__module__') and app_name in pattern.callback.__module__:
                    urls.append({
                        'pattern': prefix + str(pattern.pattern),
                        'name': pattern.name,
                        'view_name': pattern.callback.__name__ if hasattr(pattern.callback, '__name__') else None,
                        'module': pattern.callback.__module__ if hasattr(pattern.callback, '__module__') else None,
                    })
            elif isinstance(pattern, URLResolver):
                # Recursively extract from included URLconfs
                new_prefix = prefix + str(pattern.pattern)
                extract_urls(pattern.url_patterns, new_prefix)
    
    extract_urls(resolver.url_patterns)
    return urls

def discover_app_templates(app_path):
    """Discover all templates in an app"""
    templates = []
    template_dir = os.path.join(app_path, 'templates')
    
    if os.path.exists(template_dir):
        for root, dirs, files in os.walk(template_dir):
            for file in files:
                if file.endswith(('.html', '.htm')):
                    # Get relative path from templates directory
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, template_dir)
                    templates.append(relative_path)
    
    return templates