from django.core.management.base import BaseCommand
from AnalyticsModel.services import collect_system_metrics

class Command(BaseCommand):
    help = 'Collect system metrics'

    def handle(self, *args, **options):
        collect_system_metrics()
        self.stdout.write(self.style.SUCCESS('Successfully collected system metrics'))