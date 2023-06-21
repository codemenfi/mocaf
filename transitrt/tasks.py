import logging
from transitrt.exceptions import CommonTaskFailure
from transitrt.rt_import import make_importer
from celery import shared_task


logger = logging.getLogger(__name__)


importer_instances = {}


def fetch_live_locations(importer_id):
    rt_importer = importer_instances.get(importer_id)
    if rt_importer is None:
        logger.info('Initializing transitrt importer: %s' % rt_importer)
        rt_importer = make_importer(importer_id)
        importer_instances[importer_id] = rt_importer

    logger.info('Reading transit locations for %s' % importer_id)
    rt_importer.update_from_url()


@shared_task(ignore_result=True, throws=(CommonTaskFailure,))
def fetch_live_locations_tampere(importer_id):
    assert importer_id == 'tampere'
    fetch_live_locations(importer_id)


@shared_task(ignore_result=True, throws=(CommonTaskFailure,))
def fetch_live_locations_rata(importer_id):
    assert importer_id == 'rata'
    fetch_live_locations(importer_id)
