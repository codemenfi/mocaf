from django.core.management.base import BaseCommand, CommandError
from trips_ingest.processor import EventProcessor


class Command(BaseCommand):
    help = 'Ingest received data'


    def handle(self, *args, **options):
        processor = EventProcessor()
        processor.process_events()
