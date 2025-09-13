import json
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path

class Command(BaseCommand):
    help = 'Test analytics configuration and show current status'

    def add_arguments(self, parser):
        parser.add_argument('--verbose', action='store_true', help='Show detailed configuration information')

    def handle(self, *args, **options):
        self.stdout.write("🔍 Analytics Configuration Test")
        self.stdout.write("=" * 50)
        
        # Test config loading
        try:
            from app.config_utils import config_manager, is_analytics_enabled, get_analytics_sample_rate
            config = config_manager.load_config()
            self.stdout.write(self.style.SUCCESS("✅ Config system loaded successfully"))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Config system failed to load: {e}"))
            return
        
        # Show analytics configuration
        analytics_config = config.get('analytics', {})
        self.stdout.write(f"\n📊 Analytics Configuration:")
        self.stdout.write(f"  Enabled: {analytics_config.get('enabled', 'Not set')}")
        self.stdout.write(f"  Sample Rate: {analytics_config.get('sample_rate', 'Not set')}")
        self.stdout.write(f"  GeoIP Enabled: {analytics_config.get('geoip_enabled', 'Not set')}")
        self.stdout.write(f"  Session Tracking: {analytics_config.get('session_tracking', 'Not set')}")
        self.stdout.write(f"  Error Tracking: {analytics_config.get('error_tracking', 'Not set')}")
        
        # Test middleware configuration
        self.stdout.write(f"\n🔧 Middleware Configuration:")
        try:
            from AnalyticsModel.middleware import AnalyticsMiddleware
            self.stdout.write(self.style.SUCCESS("✅ AnalyticsMiddleware imported successfully"))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ AnalyticsMiddleware import failed: {e}"))
        
        # Test views configuration
        self.stdout.write(f"\n👁️ Views Configuration:")
        try:
            from AnalyticsModel.views import is_analytics_enabled as views_enabled
            self.stdout.write(self.style.SUCCESS("✅ Analytics views imported successfully"))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Analytics views import failed: {e}"))
        
        # Test settings integration
        self.stdout.write(f"\n⚙️ Settings Integration:")
        self.stdout.write(f"  ANALYTICS_ENABLED: {getattr(settings, 'ANALYTICS_ENABLED', 'Not set')}")
        self.stdout.write(f"  ANALYTICS_SAMPLE_RATE: {getattr(settings, 'ANALYTICS_SAMPLE_RATE', 'Not set')}")
        self.stdout.write(f"  GEOIP_PATH: {getattr(settings, 'GEOIP_PATH', 'Not set')}")
        
        # Test actual functionality
        self.stdout.write(f"\n🧪 Functionality Tests:")
        
        # Test analytics enabled check
        try:
            enabled = is_analytics_enabled()
            self.stdout.write(f"  Analytics Enabled Check: {enabled}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Analytics Enabled Check: Failed - {e}"))
        
        # Test sample rate check
        try:
            sample_rate = get_analytics_sample_rate()
            self.stdout.write(f"  Sample Rate Check: {sample_rate}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Sample Rate Check: Failed - {e}"))
        
        # Test GeoIP path
        geoip_path = getattr(settings, 'GEOIP_PATH', None)
        if geoip_path:
            geoip_file = Path(geoip_path) / 'GeoLite2-City.mmdb'
            if geoip_file.exists():
                self.stdout.write(self.style.SUCCESS(f"  GeoIP Database: Found at {geoip_file}"))
            else:
                self.stdout.write(self.style.WARNING(f"  GeoIP Database: Path exists but file not found at {geoip_file}"))
        else:
            self.stdout.write(self.style.WARNING("  GeoIP Database: No path configured"))
        
        # Show current config values
        if options['verbose']:
            self.stdout.write(f"\n📄 Full Analytics Config:")
            self.stdout.write(json.dumps(analytics_config, indent=2))
        
        # Summary
        self.stdout.write(f"\n📋 Summary:")
        if analytics_config.get('enabled', False):
            self.stdout.write(self.style.SUCCESS("✅ Analytics is ENABLED and should be working"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Analytics is DISABLED - no data will be collected"))
        
        if analytics_config.get('geoip_enabled', False):
            self.stdout.write(self.style.SUCCESS("✅ GeoIP tracking is ENABLED"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ GeoIP tracking is DISABLED - no location data"))
        
        if analytics_config.get('session_tracking', False):
            self.stdout.write(self.style.SUCCESS("✅ Session tracking is ENABLED"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Session tracking is DISABLED - no user session data"))
        
        if analytics_config.get('error_tracking', False):
            self.stdout.write(self.style.SUCCESS("✅ Error tracking is ENABLED"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Error tracking is DISABLED - no error data"))
        
        self.stdout.write(f"\n🎯 To change configuration, use:")
        self.stdout.write(f"  python src/manage.py editConfig --key 'analytics.enabled' --value 'false'")
        self.stdout.write(f"  python src/manage.py editConfig --key 'analytics.sample_rate' --value '0.5'")
        self.stdout.write(f"  python src/manage.py editConfig --key 'analytics.geoip_enabled' --value 'false'")
