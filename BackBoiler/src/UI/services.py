# views.py - Updated version with more detailed information
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
import json
import psutil
import datetime
from .daemon_manager import DaemonManager
from RateLimitModel.models import api_search_rate_limit, api_rate_limit




class DaemonManagerView(LoginRequiredMixin, View):
    """Main view for the daemon manager UI"""
    def get(self, request):
        return render(request, 'daemon_manager/index.html')

@method_decorator(csrf_exempt, name='dispatch')
class DaemonServiceView(LoginRequiredMixin, View):
    def __init__(self):
        super().__init__()
        self.manager = DaemonManager()
    
    def get(self, request):
        """List all services with detailed information"""
        services = self.manager.list_services()
        
        # Enrich service data with additional information
        enriched_services = []
        for service in services:
            enriched = {
                'name': service['name'],
                'status': service['status'],
                'enabled': service.get('enabled', False),
                'description': service.get('description', ''),
                'pid': service.get('pid'),
                'command': service.get('command', ''),
            }
            
            # Try to get process information if service is running
            if enriched['pid'] and enriched['status'] == 'running':
                try:
                    process = psutil.Process(enriched['pid'])
                    enriched['memory'] = f"{process.memory_info().rss / 1024 / 1024:.1f} MB"
                    enriched['cpu'] = f"{process.cpu_percent(interval=0.1):.1f}%"
                    enriched['last_started'] = datetime.datetime.fromtimestamp(
                        process.create_time()
                    ).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            
            # Get recent logs (last 10 lines)
            enriched['logs'] = self.manager.get_service_logs(service['name'], lines=10)
            
            enriched_services.append(enriched)
        
        return JsonResponse({'services': enriched_services})
    
    def post(self, request):
        """Create a new service"""
        try:
            data = json.loads(request.body)
            service_name = data.get('name')
            config = data.get('config')
            
            if not service_name or not config:
                return JsonResponse({'error': 'Missing required fields'}, status=400)
            
            # Validate service name
            import re
            if not re.match(r'^[a-zA-Z0-9-_]+$', service_name):
                return JsonResponse({'error': 'Invalid service name format'}, status=400)
            
            success = self.manager.create_service(service_name, config)
            return JsonResponse({'return': success})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class DaemonServiceDetailView(LoginRequiredMixin, View):
    def __init__(self):
        super().__init__()
        self.manager = DaemonManager()
    
    def post(self, request, service_name, action):
        """Perform action on a service"""
        actions = {
            'start': self.manager.start_service,
            'stop': self.manager.stop_service,
            'enable': self.manager.enable_service,
            'disable': self.manager.disable_service,
        }
        
        if action not in actions:
            return JsonResponse({'error': 'Invalid action'}, status=400)
        
        try:
            success = actions[action](service_name)
            return JsonResponse({'return': success})
        except Exception as e:
            return JsonResponse({'error': str(e), 'return': False}, status=500)
    
    def delete(self, request, service_name):
        """Delete a service"""
        try:
            success = self.manager.delete_service(service_name)
            return JsonResponse({'return': success})
        except Exception as e:
            return JsonResponse({'error': str(e), 'return': False}, status=500)