import logging
from celery import shared_task
from django.core import management

logger = logging.getLogger(__name__)


@shared_task
def generate_stats_task():
    logger.info("Generating stats")

    try:
        management.call_command("generate_stats", "--od", "--poi", "--lengths")
    except Exception as e:
        logger.error(e)
        logger.error("Generating stats failed")
