import logging
from celery import shared_task
from django.core import management

logger = logging.getLogger(__name__)


# @shared_task
# def generate_stats_command():
#     logger.log("Generating stats")
