import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
import re

class Command(BaseCommand):
    help = 'Edit project configuration in config.json file'

    def add_arguments(self, parser):
        parser.add_argument('--key', type=str, help='Configuration key to edit (e.g., project.name)')
        parser.add_argument('--value', type=str, help='New value for the configuration key')
        parser.add_argument('--list', action='store_true', help='List all configuration values')
        parser.add_argument('--reset', action='store_true', help='Reset config.json to default values')
        parser.add_argument('--show', action='store_true', help='Show current configuration')

    def handle(self, *args, **options):
        config_file = Path(settings.BASE_DIR) / 'app' / 'config.json'
        
        if not config_file.exists():
            self.stdout.write(self.style.ERROR(f"Config file not found: {config_file}"))
            self.stdout.write("Creating default config.json...")
            self._create_default_config(config_file)
        
        if options['list']:
            self._list_config(config_file)
        elif options['show']:
            self._show_config(config_file)
        elif options['reset']:
            self._reset_config(config_file)
        elif options['key'] and options['value']:
            self._edit_config(config_file, options['key'], options['value'])
        else:
            self._interactive_edit(config_file)

    def _create_default_config(self, config_file):
        """Create default config.json file"""
        default_config = {
            "project": {
                "name": "TempBoiler",
                "display_name": "TempBoiler",
                "description": "Django Boilerplate with Advanced UI & Analytics",
                "version": "1.0.0",
                "author": "Pouya Soltani",
                "email": "pouyasoltani81@gmail.com",
                "website": "https://pouyasoltani.com",
                "github": "https://github.com/pouyasolltani81/TempBoiler"
            },
            "ui": {
                "theme": "light",
                "default_language": "en",
                "supported_languages": ["en", "fa"],
                "company_logo": "",
                "favicon": "",
                "primary_color": "#3B82F6",
                "secondary_color": "#6B7280"
            },
            "analytics": {
                "enabled": True,
                "sample_rate": 1.0,
                "geoip_enabled": True,
                "session_tracking": True,
                "error_tracking": True
            },
            "api": {
                "title": "TempBoiler API",
                "description": "API documentation for TempBoiler project",
                "version": "v1",
                "contact_name": "Pouya Soltani",
                "contact_email": "pouyasoltani81@gmail.com"
            },
            "database": {
                "default": "sqlite:///src/dbs/main.sqlite3",
                "logs": "sqlite:///src/dbs/Logs.sqlite3"
            },
            "security": {
                "debug": True,
                "allowed_hosts": ["*"],
                "cors_enabled": True,
                "csrf_enabled": True
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(self.style.SUCCESS(f"✅ Created default config.json at {config_file}"))

    def _load_config(self, config_file):
        """Load configuration from file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading config: {e}"))
            return None

    def _save_config(self, config_file, config):
        """Save configuration to file"""
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error saving config: {e}"))
            return False

    def _list_config(self, config_file):
        """List all configuration keys"""
        config = self._load_config(config_file)
        if not config:
            return
        
        self.stdout.write("\n📋 Configuration Keys:")
        self.stdout.write("=" * 60)
        self._print_config_keys(config, "")

    def _print_config_keys(self, config, prefix):
        """Recursively print configuration keys"""
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self.stdout.write(f"  {full_key}/")
                self._print_config_keys(value, full_key)
            else:
                value_str = str(value)
                if isinstance(value, list):
                    value_str = f"[{', '.join(map(str, value))}]"
                elif isinstance(value, bool):
                    value_str = str(value).lower()
                self.stdout.write(f"  {full_key}: {value_str}")

    def _show_config(self, config_file):
        """Show current configuration"""
        config = self._load_config(config_file)
        if not config:
            return
        
        self.stdout.write("\n📄 Current Configuration:")
        self.stdout.write("=" * 60)
        self.stdout.write(json.dumps(config, indent=2, ensure_ascii=False))

    def _reset_config(self, config_file):
        """Reset config to default values"""
        self.stdout.write("🔄 Resetting configuration to defaults...")
        self._create_default_config(config_file)
        self.stdout.write(self.style.SUCCESS("✅ Configuration reset successfully!"))

    def _edit_config(self, config_file, key_path, value):
        """Edit a specific configuration key"""
        config = self._load_config(config_file)
        if not config:
            return
        
        # Parse the value based on context
        parsed_value = self._parse_value(value)
        
        # Set the value
        keys = key_path.split('.')
        current = config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = parsed_value
        
        # Save the config
        if self._save_config(config_file, config):
            self.stdout.write(self.style.SUCCESS(f"✅ Updated {key_path} = {parsed_value}"))
        else:
            self.stdout.write(self.style.ERROR("❌ Failed to save configuration"))

    def _parse_value(self, value_str):
        """Parse string value to appropriate type"""
        # Try to parse as boolean
        if value_str.lower() in ['true', 'false']:
            return value_str.lower() == 'true'
        
        # Try to parse as number
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
        
        # Try to parse as list
        if value_str.startswith('[') and value_str.endswith(']'):
            try:
                items = value_str[1:-1].split(',')
                return [item.strip().strip('"\'') for item in items if item.strip()]
            except:
                pass
        
        # Return as string
        return value_str

    def _interactive_edit(self, config_file):
        """Interactive configuration editor"""
        config = self._load_config(config_file)
        if not config:
            return
        
        self.stdout.write("\n🎛️  Interactive Configuration Editor")
        self.stdout.write("=" * 50)
        self.stdout.write("Available commands:")
        self.stdout.write("  list          - Show all configuration keys")
        self.stdout.write("  show          - Show current configuration")
        self.stdout.write("  edit <key> <value> - Edit a specific key")
        self.stdout.write("  reset         - Reset to default values")
        self.stdout.write("  quit          - Exit editor")
        self.stdout.write("  help          - Show this help")
        
        while True:
            try:
                command = input("\nconfig> ").strip()
                
                if command.lower() in ['quit', 'exit', 'q']:
                    break
                elif command.lower() == 'help':
                    self.stdout.write("Available commands:")
                    self.stdout.write("  list          - Show all configuration keys")
                    self.stdout.write("  show          - Show current configuration")
                    self.stdout.write("  edit <key> <value> - Edit a specific key")
                    self.stdout.write("  reset         - Reset to default values")
                    self.stdout.write("  quit          - Exit editor")
                    self.stdout.write("  help          - Show this help")
                elif command.lower() == 'list':
                    self._list_config(config_file)
                elif command.lower() == 'show':
                    self._show_config(config_file)
                elif command.lower() == 'reset':
                    self._reset_config(config_file)
                    config = self._load_config(config_file)
                elif command.startswith('edit '):
                    parts = command[5:].split(' ', 1)
                    if len(parts) == 2:
                        key, value = parts
                        self._edit_config(config_file, key, value)
                        config = self._load_config(config_file)
                    else:
                        self.stdout.write(self.style.ERROR("Usage: edit <key> <value>"))
                else:
                    self.stdout.write(self.style.WARNING("Unknown command. Type 'help' for available commands."))
                    
            except KeyboardInterrupt:
                self.stdout.write("\n\n👋 Goodbye!")
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
        
        self.stdout.write(self.style.SUCCESS("✅ Configuration editor closed."))
