from django.core.management.base import BaseCommand, CommandError
from dateutil.parser import parse
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils.timezone import localdate

from poll.models import SurveyInfo
from poll.reports.survey_report import export_survey_trips, export_survey_trips_json


class Command(BaseCommand):
    help = "Generate Excel report for survey trips"

    def add_arguments(self, parser):
        parser.add_argument("--survey", type=str)
        parser.add_argument("--format", type=str)

    def handle(self, *args, **options):
        survey = options["survey"]
        format = options["format"]

        if not survey:
            raise CommandError("Survey id is required")

        survey = SurveyInfo.objects.get(pk=survey)

        if format == "json":
            export_survey_trips_json(survey)
        else:
            export_survey_trips(survey)
