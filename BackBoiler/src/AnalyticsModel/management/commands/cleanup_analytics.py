from django.core.management.base import BaseCommand
from django.db import transaction
from AnalyticsModel.models import APIRequest, APIEndpoint, UserSession, SystemMetrics, ErrorLog

class Command(BaseCommand):
    help = 'Clean all analytics data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompt',
        )
        parser.add_argument(
            '--keep-endpoints',
            action='store_true',
            help='Keep endpoint definitions',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            confirm = input('This will delete ALL analytics data. Are you sure? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return

        with transaction.atomic():
            # Delete all API requests
            count = APIRequest.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {count} API requests'))

            # Delete all user sessions
            count = UserSession.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {count} user sessions'))

            # Delete all error logs
            count = ErrorLog.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {count} error logs'))

            # Delete all system metrics
            count = SystemMetrics.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {count} system metrics'))

            # Delete endpoints unless specified to keep
            if not options['keep_endpoints']:
                count = APIEndpoint.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'✓ Deleted {count} API endpoints'))
            else:
                self.stdout.write(self.style.WARNING('↷ Kept API endpoints'))

            # Clear cache
            from django.core.cache import cache
            cache.clear()
            self.stdout.write(self.style.SUCCESS('✓ Cleared cache'))

        self.stdout.write(self.style.SUCCESS('\n✨ All analytics data cleaned successfully!'))