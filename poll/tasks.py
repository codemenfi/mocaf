import logging
from celery import shared_task

from .generate import SurveyTripGenerator


logger = logging.getLogger(__name__)
generator = SurveyTripGenerator()


@shared_task
def generate_new_survey_trips():
    logger.info("Generating new survey trips")
    generator.generate_new_trips()
