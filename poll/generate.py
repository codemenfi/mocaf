from datetime import datetime, timedelta, date
import logging
from typing import Optional
import sentry_sdk
import geopandas as gpd
import requests
from sqlalchemy.util import has_compiled_ext

from calc.trips import (
    LOCAL_2D_CRS,
    read_locations,
    read_uuids,
    split_trip_legs,
    filter_trips,
)

from utils.perf import PerfCounter
from django.db import transaction, connection
from django.db.models import Q, Exists, Max, OuterRef
from django.contrib.gis.gdal import SpatialReference, CoordTransform
from django.contrib.gis.geos import Point
from django.utils import timezone
from psycopg2.extras import execute_values
from trips.models import Device
from trips_ingest.models import Location
from poll.models import (
    MUNICIPALITY_CHOICES,
    MUNICIPALITY_OTHER,
    SurveyInfo,
    Trips,
    Legs,
    LegsLocation,
    Partisipants,
)


logger = logging.getLogger(__name__)

LEGS_LOCATION_TABLE = LegsLocation._meta.db_table

local_crs = SpatialReference(LOCAL_2D_CRS)
gps_crs = SpatialReference(4326)
coord_transform = CoordTransform(local_crs, gps_crs)


# Transform to GPS coordinates
def make_point(x, y):
    pnt = Point(x, y, srid=LOCAL_2D_CRS)
    pnt.transform(coord_transform)
    return pnt


def generate_leg_location_rows(leg, df):
    rows = df.apply(
        lambda row: (
            leg.id,
            row.lon,
            row.lat,
            "%s" % str(row.time),
            row.speed,
        ),
        axis=1,
    )
    return list(rows.values)


class GeneratorError(Exception):
    pass


class SurveyTripGenerator:
    def __init__(self, force=False):
        self.force = force

        self.atype_to_survey_mode = {
            "walking": "walk",
            "on_foot": "walk",
            "in_vehicle": "car_driver",
            "running": "walk",
            "on_bicycle": "bicycle",
            "bus": "bus",
            "tram": "tram",
            "train": "train",
        }

    def insert_survey_leg_locations(self, rows):
        # Having "None" as the speed column is a periodically recurring
        # issue. Raise error to continue with other uuids if None found
        # in speed column
        try:
            next(x for x in rows if x[4] is None)
            raise GeneratorError("Encountered invalid value None as speed for leg")
        except StopIteration:
            pass
        pc = PerfCounter("save_locations", show_time_to_last=True)
        query = f"""INSERT INTO {LEGS_LOCATION_TABLE} (
            leg_id, loc, time, speed
        ) VALUES %s"""

        with connection.cursor() as cursor:
            pc.display("after cursor")
            value_template = """(
                    %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s :: timestamptz,
                    %s
            )"""
            execute_values(
                cursor, query, rows, template=value_template, page_size=10000
            )

        pc.display("after insert")

    def save_survey_leg(self, trip, df, last_ts, pc):
        start = df.iloc[0][["time", "x", "y"]]
        end = df.iloc[-1][["time", "x", "y"]]
        received_at = df.iloc[-1].created_at

        leg_length = df["distance"].sum()

        # Ensure trips are ordered properly
        assert start.time >= last_ts and end.time >= last_ts

        atype = df.iloc[0].atype
        mode = trip.partisipant.default_survey_mode(atype)

        if not mode:
            mode = self.atype_to_survey_mode[atype]

        leg = Legs(
            trip_id=trip.id,
            transport_mode=mode,
            trip_length=leg_length,
            start_time=start.time,
            end_time=end.time,
            start_loc=make_point(start.x, start.y),
            end_loc=make_point(end.x, end.y),
            received_at=received_at,
        )
        leg.save()
        rows = generate_leg_location_rows(leg, df)
        pc.display(str(leg))

        return rows, end.time

    def save_survey_trip_town(self, tripObj, df, starttown):
        if starttown:
            time_loc = df.iloc[0][["time", "x", "y"]]
        else:
            time_loc = df.iloc[-1][["time", "x", "y"]]
        mycoord = SpatialReference(4326)
        gcoord = SpatialReference(LOCAL_2D_CRS)
        trans = CoordTransform(gcoord, mycoord)

        pnt = Point(time_loc.x, time_loc.y, srid=LOCAL_2D_CRS)
        pnt.transform(trans)
        lat = pnt.y
        lon = pnt.x
        coord_link = (
            "https://nominatim.openstreetmap.org/reverse?format=json&lat="
            + str(lat)
            + "&lon="
            + str(lon)
            + "&zoom=10&addressdetails=10"
        )
        headers = {"User-Agent": "mocaf"}
        request_json = requests.get(coord_link, headers=headers).json()

        # towndict = {"Tampere": "Tampere", "Kangasala": "Kangasala", "Pirkkala": "Pirkkala",
        #             "Nokia": "Nokia", "Ylöjärvi": "Ylojarvi", "Lempäälä": "Lempaala",
        #             "Vesilahti": "Vesilahti", "Orivesi": "Orivesi"}

        town = MUNICIPALITY_OTHER

        if request_json.get("name"):
            start_town = request_json.get("name")

            municipalities = [x[0] for x in MUNICIPALITY_CHOICES]
            if start_town in municipalities:
                town = start_town

        if starttown:
            tripObj.start_municipality = town
        else:
            tripObj.end_municipality = town

        tripObj.save()

        return

    def save_trip(self, device, df, default_variants, uuid, partisipant):
        pc = PerfCounter("generate_trips", show_time_to_last=True)
        if not len(df):
            print("No samples, returning")
            return

        pc.display("start")

        min_time = df.time.min()
        max_time = df.time.max()

        df = gpd.GeoDataFrame(
            df, geometry=gpd.points_from_xy(df.x, df.y, crs=LOCAL_2D_CRS)
        )
        pc.display("after create gdf for %d points" % len(df))
        df["geometry"] = df["geometry"].to_crs(4326)
        df["lon"] = df.geometry.x
        df["lat"] = df.geometry.y
        pc.display("after crs for %d points" % len(df))

        if partisipant is None:
            logger.info("No partisipant for device %s" % device)
            return

        # Delete trips that overlap with our data
        overlap = Q(end_time__gte=min_time) & Q(end_time__lte=max_time)
        overlap |= Q(start_time__gte=min_time) & Q(start_time__lte=max_time)
        legs = Legs.objects.filter(trip__partisipant=partisipant).filter(overlap)

        if not self.force:
            if legs.filter(Q(original_leg=False)).exists():
                pc.display("Legs have user corrected elements, not deleting")
                logger.info("Legs have user corrected elements, not deleting")
                return

        if not self.force:
            if (
                partisipant.trips_set.filter(legs__in=legs)
                .filter(Q(original_trip=False) | ~Q(purpose="tyhja"))
                .exists()
            ):
                logger.info("Trips have user corrected elements, not deleting")
                pc.display("Trips have user corrected elements, not deleting")
                return

        count = Trips.objects.filter(legs__in=legs, partisipant=partisipant).delete()

        # Create trips
        survey_enabled = Device.objects.get(uuid=uuid).survey_enabled

        if partisipant is None:
            return


        # Don't generate trips outside survey period
        start_date = min_time.date()
        if start_date > partisipant.end_date or start_date < partisipant.start_date:
            return


        if survey_enabled:
            all_rows_survey = []
            survey_trip = Trips(
                start_time=min_time, end_time=max_time, partisipant_id=partisipant.id
            )
            survey_trip.save()
            pc.display("survey trip %d saved" % survey_trip.id)
            first_leg = True
            leg_ids = df.leg_id.unique()
            leg_df = None
            last_ts = df.time.min()
            for leg_id in leg_ids:
                leg_df = df[df.leg_id == leg_id]

                if first_leg:
                    first_leg = False
                    self.save_survey_trip_town(survey_trip, leg_df, True)

                leg_rows_survey, last_ts = self.save_survey_leg(
                    survey_trip, leg_df, last_ts, pc
                )
                all_rows_survey += leg_rows_survey

            if not first_leg and leg_df is not None:
                self.save_survey_trip_town(survey_trip, leg_df, False)

            pc.display("generated %d survey legs" % len(leg_ids))
            self.insert_survey_leg_locations(all_rows_survey)
            pc.display("survey trip %d save done" % survey_trip.id)

    def begin(self):
        transaction.set_autocommit(False)

    def process_trip(self, device, df, uuid, partisipant):
        pc = PerfCounter("process_trip")
        logger.info(
            "%s: %s: trip with %d samples" % (str(device), df.time.min(), len(df))
        )
        df = filter_trips(df)
        pc.display("filter done")

        # Use the fixed versions of columns
        df["atype"] = df["atypef"]
        df["x"] = df["xf"]
        df["y"] = df["yf"]

        df = split_trip_legs(connection, str(device.uuid), df, False, True, True)
        pc.display("legs split")
        if df is None:
            logger.info("%s: No legs for trip" % str(device))
            return
        with transaction.atomic():
            self.save_trip(device, df, device._default_variants, uuid, partisipant)
        pc.display("trip saved")

    def generate_trips(self, uuid, start_time, end_time, generation_started_at=None):
        device: Optional[Device] = Device.objects.filter(uuid=uuid).first()
        if device is None:
            raise GeneratorError("Device %s not found" % uuid)

        current_survey = SurveyInfo.objects.filter(
            start_day__lte=timezone.now(), end_day__gte=timezone.now()
        ).first()

        if current_survey is None:
            return

        partisipant = (
            Partisipants.objects.filter(device=device, survey_info=current_survey)
            .order_by("-registered_to_survey_at")
            .first()
        )
        if partisipant is None:
            return

        if partisipant.approved:
            return

        if start_time is not None and start_time.date() > partisipant.end_date:
            return
        

        device._default_variants = {
            x.mode: x.variant for x in device.default_mode_variants.all()
        }

        pc = PerfCounter("update trips for %s" % uuid, show_time_to_last=True)
        df = read_locations(connection, uuid, start_time=start_time, end_time=end_time)
        if df is None or not len(df):
            if generation_started_at is not None:
                partisipant.last_processed_data_received_at = generation_started_at
                partisipant.save(update_fields=["last_processed_data_received_at"])
            return
        pc.display("read done, got %d rows" % len(df))

        for trip_id in df.trip_id.unique():
            trip_df = df[df.trip_id == trip_id].copy()
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("start_time", trip_df.time.min().isoformat())
                scope.set_tag("end_time", trip_df.time.max().isoformat())
                self.process_trip(device, trip_df, uuid, partisipant)
                scope.clear()

        if generation_started_at is not None:
            partisipant.last_processed_data_received_at = generation_started_at
            partisipant.save(update_fields=["last_processed_data_received_at"])
        transaction.commit()
        pc.display("trips generated")

    def find_uuids_with_new_samples(self, min_received_at: Optional[datetime] = None):
        if not min_received_at:
            min_received_at = timezone.now() - timedelta(days=7)

        current_survey = SurveyInfo.objects.filter(
            start_day__lte=timezone.now(), end_day__gte=timezone.now()
        ).first()

        if current_survey is None:
            return []

        device_uuids = (
            Device.objects.annotate(
                has_active_partisipant=Exists(
                    Partisipants.objects.filter(
                        device=OuterRef("pk"), survey_info=current_survey
                    )
                )
            )
            .filter(has_active_partisipant=True)
            .values("uuid")
        )

        uuid_qs = (
            Location.objects.filter(deleted_at__isnull=True, time__gte=min_received_at)
            .filter(uuid__in=device_uuids)
            .values("uuid")
            .annotate(newest_created_at=Max("created_at"))
            .order_by()
        )
        uuids = uuid_qs.values("uuid")

        devices = (
            Device.objects.annotate(
                last_leg_received_at=Max("partisipants__trips__legs__received_at"),
                last_leg_end_time=Max("partisipants__trips__legs__end_time"),
                survey_last_processed_data_received_at=Max(
                    "partisipants__last_processed_data_received_at"
                ),
            )
            .values(
                "uuid",
                "last_leg_received_at",
                "last_leg_end_time",
                "survey_last_processed_data_received_at",
            )
            .filter(uuid__in=uuids)
        )
        dev_by_uuid = {
            x["uuid"]: dict(
                last_leg_received_at=x["last_leg_received_at"],
                last_leg_end_time=x["last_leg_end_time"],
                last_data_processed_at=x["survey_last_processed_data_received_at"],
            )
            for x in devices
        }

        uuids = uuid_qs.values("uuid", "newest_created_at")

        uuids_to_process = []
        for row in uuids:
            uuid = row["uuid"]
            newest_created_at = row["newest_created_at"]

            dev = dev_by_uuid.get(uuid)
            end_time = min_received_at
            if dev:
                if (
                    dev["last_leg_received_at"]
                    and newest_created_at <= dev["last_leg_received_at"]
                ):
                    continue
                if (
                    dev["last_data_processed_at"]
                    and newest_created_at <= dev["last_data_processed_at"]
                ):
                    continue
                if (
                    dev["last_leg_end_time"]
                    and dev["last_leg_end_time"] > min_received_at
                ):
                    end_time = dev["last_leg_end_time"]

            uuids_to_process.append([uuid, end_time])
        return uuids_to_process

    def generate_new_trips(self, only_uuid=None):
        now = timezone.now()
        uuids = self.find_uuids_with_new_samples()
        logger.info("found %d uuids" % len(uuids))
        for uuid, last_leg_end in uuids:
            if only_uuid is not None:
                if str(uuid) != only_uuid:
                    continue
            if last_leg_end:
                start_time = last_leg_end
                end_time = now
            else:
                start_time = None
                end_time = None

            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("uuid", str(uuid))
                try:
                    self.generate_trips(
                        uuid,
                        start_time=start_time,
                        end_time=end_time,
                        generation_started_at=now,
                    )
                except GeneratorError as e:
                    sentry_sdk.capture_exception(e)

    def end(self):
        transaction.commit()
        transaction.set_autocommit(True)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    load_dotenv()
    eng = create_engine(os.getenv("DATABASE_URL"))
    conn = eng.connect()

    all_uids = read_uuids(eng)
