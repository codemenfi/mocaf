import gzip
import pytz
from django.db.models import Q
from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
from django.conf import settings


LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)


class ReceiveDataQuerySet(models.QuerySet):
    def for_uuid(self, uid):
        qs = Q(data__location__0__extras__uid=uid)
        qs |= Q(data__uid=uid)
        qs |= Q(data__userId=uid)
        return self.filter(qs)

    def by_type(self, data_type):
        if data_type == 'location':
            return self.filter(data__location__isnull=False)
        elif data_type == 'sensor':
            return self.filter(data__dataType='sensor2')
        elif data_type == 'device_info':
            return self.filter(data__dataType='device_info')
        elif data_type == 'heartbeat':
            return self.filter(data__dataType='heartbeat')


class ReceiveData(models.Model):
    data = models.JSONField()
    device = models.ForeignKey(
        'trips.Device', on_delete=models.CASCADE, null=True, related_name='receive_data'
    )
    received_at = models.DateTimeField(db_index=True)
    imported_at = models.DateTimeField(null=True, db_index=True)
    import_failed = models.BooleanField(null=True)

    objects = ReceiveDataQuerySet.as_manager()

    class Meta:
        ordering = ('received_at',)

    def __str__(self):
        received_at = self.received_at.astimezone(LOCAL_TZ)
        imported_at = self.imported_at.astimezone(LOCAL_TZ) if self.imported_at else None
        return '%s: %s (Received: %s | Imported: %s | Failed: %s)' % (
            self.get_uuid(), self.get_event_type(),
            received_at, imported_at, self.import_failed
        )

    def get_event_type(self):
        if 'location' in self.data:
            return 'location'

        data_type = self.data.get('dataType')
        if not isinstance(data_type, str):
            return 'unknown'
        if data_type == 'sensor2':
            return 'sensor'
        elif data_type == 'device_info':
            return 'device_info'
        elif data_type == 'heartbeat':
            return 'heartbeat'

    def get_uuid(self):
        loc = self.data.get('location')
        if loc:
            if 'uid' in self.data:
                return self.data['uid']
            if isinstance(loc, list):
                return loc[0].get('extras', {}).get('uid')
        if 'userId' in self.data:
            return self.data['userId']

    def process_event(self):
        from .processor import EventProcessor

        processor = EventProcessor()
        processor.process_event(self)


class ReceiveDebugLog(models.Model):
    data = models.JSONField(null=True)
    log = models.BinaryField(max_length=5*1024*1024, null=True)
    uuid = models.UUIDField()
    received_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ('received_at',)

    def __str__(self):
        return '%s, len %d (Received: %s)' % (
            self.uuid,
            len(self.log) if self.log else -1,
            self.received_at.astimezone(LOCAL_TZ)
        )

    def print(self):
        data = gzip.decompress(self.log)
        print(data.decode('utf8'))


class LocationImport(models.Model):
    id = models.IntegerField(primary_key=True)
    time = models.IntegerField(null=False)
    uid = models.CharField(max_length=50)
    lat = models.FloatField(null=True)
    lon = models.FloatField(null=True)
    acc = models.IntegerField(null=True)
    atype = models.CharField(max_length=30, null=True)
    aconf = models.IntegerField(null=True)
    speed = models.FloatField(null=True)
    heading = models.FloatField(null=True)
    ms = models.IntegerField(null=True)
    created_at = models.IntegerField(null=True)
    debug = models.IntegerField(null=True)


class DeviceImport(models.Model):
    id = models.IntegerField(primary_key=True)
    uid = models.CharField(max_length=50)
    platform = models.CharField(max_length=20, null=True)
    system_version = models.CharField(max_length=20, null=True)
    brand = models.CharField(max_length=20, null=True)
    model = models.CharField(max_length=20, null=True)
    created_at = models.IntegerField(null=True)


class HeartbeatImport(models.Model):
    id = models.IntegerField(primary_key=True)
    time = models.IntegerField(null=False)
    ms = models.IntegerField(null=True)
    uid = models.CharField(max_length=50)
    debug = models.IntegerField(null=True)


class SensorSampleImport(models.Model):
    id = models.IntegerField(primary_key=True)
    uid = models.CharField(max_length=50)
    time = models.IntegerField(null=False)
    ms = models.IntegerField(null=True)
    x = models.FloatField(null=False)
    y = models.FloatField(null=False)
    z = models.FloatField(null=False)
    type = models.CharField(null=False, max_length=20)


class ActivityTypeChoices(models.TextChoices):
    UNKNOWN = 'unknown', _('Unknown')
    STILL = 'still', _('Still')
    ON_FOOT = 'on_foot', _('On foot')
    WALKING = 'walking', _('Walking')
    RUNNING = 'running', _('Running')
    ON_BICYCLE = 'on_bicycle', _('On bicycle')
    IN_VEHICLE = 'in_vehicle', _('In vehicle')


class Location(models.Model):
    time = models.DateTimeField(primary_key=True)
    uuid = models.UUIDField()
    loc = models.PointField(null=False, srid=settings.LOCAL_SRS)
    loc_error = models.FloatField(null=True)
    atype = models.CharField(choices=ActivityTypeChoices.choices, null=True, max_length=20)
    aconf = models.FloatField(null=True)
    speed = models.FloatField(null=True)
    speed_error = models.FloatField(null=True)
    altitude = models.FloatField(null=True)
    altitude_error = models.FloatField(null=True)
    heading = models.FloatField(null=True)
    heading_error = models.FloatField(null=True)
    odometer = models.FloatField(null=True)
    is_moving = models.BooleanField(null=True)
    battery_charging = models.BooleanField(null=True)
    created_at = models.DateTimeField(null=True)
    debug = models.BooleanField(default=False)
    manual_atype = models.CharField(choices=ActivityTypeChoices.choices, null=True, max_length=20)
    sensor_data_count = models.PositiveIntegerField(null=True)
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = 'trips_ingest_location'

    def __str__(self):
        return '%s [%s]' % (self.uuid, self.time)


class DeviceHeartbeat(models.Model):
    time = models.DateTimeField()
    uuid = models.UUIDField()
    created_at = models.DateTimeField(null=True)

    class Meta:
        unique_together = ('uuid', 'time')


class SensorTypeChoices(models.TextChoices):
    ACCELEROMETER = 'acce', _('Accelerometer')
    GYROSCOPE = 'gyro', _('Gyroscope')


class SensorSample(models.Model):
    time = models.DateTimeField()
    uuid = models.UUIDField()
    x = ArrayField(models.FloatField())
    y = ArrayField(models.FloatField())
    z = ArrayField(models.FloatField())
    t = ArrayField(models.FloatField())
    type = models.CharField(max_length=20, choices=SensorTypeChoices.choices)

    class Meta:
        db_table = 'trips_ingest_sensorsample'
        unique_together = (('uuid', 'time', 'type',),)
        ordering = ('uuid', 'time')
        managed = True
