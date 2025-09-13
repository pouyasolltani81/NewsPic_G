import json
import os
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages project configuration from config.json file"""
    
    def __init__(self):
        self._config = None
        self._cache_key = 'project_config'
        self._cache_timeout = 300  # 5 minutes
    
    @property
    def config_file(self):
        """Get config file path lazily to avoid circular imports"""
        from django.conf import settings
        return Path(settings.BASE_DIR) / 'app' / 'config.json'
    
    def load_config(self):
        """Load configuration from config.json file"""
        try:
            # Try to get from cache first
            cached_config = cache.get(self._cache_key)
            if cached_config:
                return cached_config
            
            # Load from file
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Cache the config
                cache.set(self._cache_key, config, self._cache_timeout)
                self._config = config
                return config
            else:
                logger.warning(f"Config file not found: {self.config_file}")
                return self._get_default_config()
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config.json: {e}")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._get_default_config()
    
    def get(self, key_path, default=None):
        """Get a configuration value using dot notation (e.g., 'project.name')"""
        config = self.load_config()
        if not config:
            return default
        
        keys = key_path.split('.')
        value = config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_project_name(self):
        """Get the project name"""
        return self.get('project.name', 'TempBoiler')
    
    def get_display_name(self):
        """Get the project display name"""
        return self.get('project.display_name', 'TempBoiler')
    
    def get_project_description(self):
        """Get the project description"""
        return self.get('project.description', 'Django Boilerplate with Advanced UI & Analytics')
    
    def get_api_title(self):
        """Get the API title"""
        return self.get('api.title', 'TempBoiler API')
    
    def get_api_description(self):
        """Get the API description"""
        return self.get('api.description', 'API documentation for TempBoiler project')

    def get_api_version(self):
        """Get the API version"""
        return self.get('api.version', 'API documentation for TempBoiler project')

    def get_project_version(self):
        """Get the API version"""
        return self.get('project.version', 'API documentation for TempBoiler project')
    
    def get_ui_theme(self):
        """Get the default UI theme"""
        return self.get('ui.theme', 'light')
    
    def get_default_language(self):
        """Get the default language"""
        return self.get('ui.default_language', 'en')
    
    def get_supported_languages(self):
        """Get supported languages"""
        return self.get('ui.supported_languages', ['en', 'fa'])
    
    def is_analytics_enabled(self):
        """Check if analytics is enabled"""
        return self.get('analytics.enabled', True)
    
    def get_analytics_sample_rate(self):
        """Get analytics sample rate"""
        return self.get('analytics.sample_rate', 1.0)
    
    def is_debug_enabled(self):
        """Check if debug mode is enabled"""
        return self.get('security.debug', True)
    
    def get_allowed_hosts(self):
        """Get allowed hosts"""
        return self.get('security.allowed_hosts', ['*'])

    def get_logs_database(self):
        """Get logs database"""
        return self.get('database.logs', ['sqlite:///src/dbs/Logs.sqlite3'])

    def get_default_database(self):
        """Get default database"""
        return self.get('database.default', ['sqlite:///src/dbs/main.sqlite3'])
    
    def get_cors_enabled(self):
        """Get cors enabled"""
        return self.get('security.cors_enabled', [True])
    
    def get_csrf_enabled(self):
        """Get csrf enabled"""
        return self.get('security.csrf_enabled', [True])
    
    def reload_config(self):
        """Reload configuration from file and clear cache"""
        cache.delete(self._cache_key)
        self._config = None
        return self.load_config()
    
    def _get_default_config(self):
        """Return default configuration if file is not found"""
        return {
            "project": {
                "name": "TempBoiler",
                "display_name": "TempBoiler",
                "description": "Django Boilerplate with Advanced UI & Analytics",
                "version": "1.0.0"
            },
            "ui": {
                "theme": "light",
                "default_language": "en",
                "supported_languages": ["en", "fa"]
            },
            "analytics": {
                "enabled": True,
                "sample_rate": 1.0
            },
            "api": {
                "title": "TempBoiler API",
                "description": "API documentation for TempBoiler project",
                "version": "v1"
            },
            "security": {
                "debug": True,
                "allowed_hosts": ["*"]
            }
        }

# Global instance
config_manager = ConfigManager()

# Convenience functions
def get_project_name():
    """Get project name from config"""
    return config_manager.get_project_name()

def get_display_name():
    """Get project display name from config"""
    return config_manager.get_display_name()

def get_project_description():
    """Get project description from config"""
    return config_manager.get_project_description()


def get_project_version():
    """Get project description from config"""
    return config_manager.get_project_version()

def get_api_version():
    """Get api description from config"""
    return config_manager.get_api_version()

def get_api_title():
    """Get API title from config"""
    return config_manager.get_api_title()

def get_api_description():
    """Get API description from config"""
    return config_manager.get_api_description()

def get_ui_theme():
    """Get UI theme from config"""
    return config_manager.get_ui_theme()

def get_default_language():
    """Get default language from config"""
    return config_manager.get_default_language()

def get_supported_languages():
    """Get supported languages from config"""
    return config_manager.get_supported_languages()

def is_analytics_enabled():
    """Check if analytics is enabled"""
    return config_manager.is_analytics_enabled()

def get_analytics_sample_rate():
    """Get analytics sample rate from config"""
    return config_manager.get_analytics_sample_rate()

def get_logs_database():
    """Get logs database from config"""
    return config_manager.get_logs_database()

def get_default_database():
    """Get default database from config"""
    return config_manager.get_default_database()

def is_debug_enabled():
    """Check if debug mode is enabled"""
    return config_manager.is_debug_enabled()

def get_allowed_hosts():
    """Get allowed hosts from config"""
    return config_manager.get_allowed_hosts()


def get_cors_enabled():
    """Get cors  from config"""
    return config_manager.get_cors_enabled()


def get_csrf_enabled():
    """Get csrf  from config"""
    return config_manager.get_csrf_enabled()

