import logging
import json
import pytz
from datetime import datetime, timedelta
from django.db.models import Max
from django.db import transaction
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from multigtfs.models import Route

from transitrt.models import VehicleLocation


logger = logging.getLogger(__name__)


LOCAL_TZ = pytz.timezone('Europe/Helsinki')


def js_to_dt(ts):
    return LOCAL_TZ.localize(datetime.fromtimestamp(ts / 1000))


class Command(BaseCommand):
    help = 'Updates transit locations from SIRI-RT feed'

    def import_vehicle_activity(self, d):
        time = js_to_dt(d['RecordedAtTime'])
        d = d['MonitoredVehicleJourney']
        loc = Point(d['VehicleLocation']['Longitude'], d['VehicleLocation']['Latitude'], srid=4326)
        route = self.routes_by_ref[d['LineRef']['value']]
        jr = d['FramedVehicleJourneyRef']
        journey_ref = '%s:%s' % (jr['DataFrameRef']['value'], jr['DatedVehicleJourneyRef'])

        return dict(
            time=time,
            vehicle_ref=d['VehicleRef']['value'],
            route=route,
            direction_ref=d['DirectionRef']['value'],
            loc=loc,
            journey_ref=journey_ref,
            bearing=d['Bearing'],
        )

    def update_cached_locs(self, vehicle_ids):
        to_fetch = set()
        for vid in vehicle_ids:
            if vid not in self.cached_locs:
                to_fetch.add(vid)
        if not to_fetch:
            return

        locs = VehicleLocation.objects.filter(vehicle_ref__in=vehicle_ids)\
            .values('vehicle_ref', 'time').distinct('vehicle_ref')\
            .order_by('vehicle_ref', '-time')
        for x in locs:
            self.cached_locs[x['vehicle_ref']] = x['time']

    def update_from_siri(self, data):
        assert len(data) == 1
        data = data['Siri']
        assert len(data) == 1
        data = data['ServiceDelivery']

        data_ts = js_to_dt(data['ResponseTimestamp'])
        data = data['VehicleMonitoringDelivery']
        assert len(data) == 1
        data = data[0]
        resp_ts = js_to_dt(data['ResponseTimestamp'])
        assert data_ts == resp_ts
        if 'VehicleActivity' not in data:
            logger.info('No vehicle data found')
            return
        data = data['VehicleActivity']

        for act_in in data:
            act = self.import_vehicle_activity(act_in)
            if abs((data_ts - act['time']).total_seconds()) > 60:
                logger.error('Refusing too long time difference for %s (%s)' % (act['vehicle_ref'], act['time']))
                continue

            vid = act['vehicle_ref']
            last_time = self.cached_locs.get(vid)
            if last_time and last_time + timedelta(seconds=1) >= act['time']:
                continue
            self._batch_vids.add(act['vehicle_ref'])
            self._batch.append(act)

    def commit(self):
        self.update_cached_locs(self._batch_vids)
        new_objs = []
        for act in self._batch:
            vid = act['vehicle_ref']
            last_time = self.cached_locs.get(vid)
            # Ensure the new sample is fresh enough
            if last_time and last_time + timedelta(seconds=1) >= act['time']:
                continue

            new_objs.append(VehicleLocation(**act))
            self.cached_locs[vid] = act['time']

        self._batch = []
        self._batch_vids = set()

        logger.info('Saving %d observations' % len(new_objs))
        if not new_objs:
            return
        VehicleLocation.objects.bulk_create(new_objs)
        transaction.commit()

    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+', type=str)

    def handle(self, *args, **options):
        self.routes_by_ref = {r.route_id: r for r in Route.objects.all()}
        self.cached_locs = {}
        transaction.set_autocommit(False)
        file_count = 0
        self._batch = []
        self._batch_vids = set()

        for fn in options['files']:
            with open(fn, 'r') as f:
                data = json.load(f)
            logger.info('Importing from %s' % fn)
            self.update_from_siri(data)
            file_count += 1
            if file_count == 100:
                self.commit()
                file_count = 0
        if file_count:
            self.commit()
        transaction.set_autocommit(True)
