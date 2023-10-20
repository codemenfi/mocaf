from django.core.management.base import BaseCommand, CommandError
from dateutil.parser import parse
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils.timezone import localdate

from feedback.models import DeviceFeedback
from feedback.reports.feedback_report import export_feedbacks


class Command(BaseCommand):
    help = "Generate Excel report of user feedbacks"

    # def add_arguments(self, parser):
    #     parser.add_argument("--survey", type=str)
    #     parser.add_argument("--format", type=str)

    def handle(self, *args, **options):
        # survey = options["survey"]
        # format = options["format"]

        feedbacks = DeviceFeedback.objects.filter(trip__isnull=False, leg__isnull=False)
        export_feedbacks(feedbacks)
