
from django.core.management.base import BaseCommand
from AnalyticsModel.models import SystemMetrics

class Command(BaseCommand):
    help = "Clears all SystemMetrics data from the database"

    def handle(self, *args, **options):
        total = SystemMetrics.objects.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No SystemMetrics data found."))
            return

        SystemMetrics.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {total} SystemMetrics records."))
