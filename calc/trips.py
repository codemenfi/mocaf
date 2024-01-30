import os
import logging
import numba
import numpy as np
from datetime import date, datetime, timedelta
import pandas as pd
from utils.perf import PerfCounter

from .dragimm import filter_trajectory, filters as transport_modes
from .transitest import transit_prob_ests_糞


TABLE_NAME = 'trips_ingest_location'
TRANSIT_TABLE = 'transitrt_vehiclelocation'
OSM_ROADS_TABLE = 'planet_osm_line'
LOCAL_TZ = 'Europe/Helsinki'

MINS_BETWEEN_TRIPS = 20
MIN_DISTANCE_MOVED_IN_TRIP = 200
MIN_SAMPLES_PER_LEG = 15

DAYS_TO_FETCH = 100
LOCAL_2D_CRS = 3067

logger = logging.getLogger(__name__)


def prepare_sql_statements(conn):
    with conn.cursor() as curs:
        # Check if we have prepared the statement for this DB session before.
        curs.execute(
            'SELECT COUNT(*) FROM pg_prepared_statements WHERE name = %(name)s',
            dict(name='read_locations')
        )
        rows = curs.fetchall()
        if rows[0][0]:
            return

        path = os.path.dirname(__file__)
        fn = os.path.join(path, 'sql', 'read_locations.sql')
        query = open(fn, 'r').read()
        with conn.cursor() as curs:
            curs.execute(query)


def read_locations(conn, uid, start_time=None, end_time=None, include_all=False):
    pc = PerfCounter('read %s' % uid, show_time_to_last=True)

    prepare_sql_statements(conn)

    if end_time is None:
        end_time = datetime.utcnow()

    if start_time is None:
        if isinstance(end_time, datetime):
            start_time = end_time - timedelta(days=14)
        else:
            start_time = (date.today() - timedelta(days=14)).isoformat()

    params = dict(uuid=uid, start_time=start_time, end_time=end_time)
    query = 'EXECUTE read_locations(%(uuid)s, %(start_time)s, %(end_time)s)'
    df = pd.read_sql_query(query, conn, params=params)
    pc.display('query done, got %d rows' % len(df))

    df['time'] = pd.to_datetime(df.time, utc=True)
    df['timediff'] = df['time'].diff().dt.total_seconds().fillna(value=0)
    df['new_trip'] = df['timediff'] > MINS_BETWEEN_TRIPS * 60
    df['trip_id'] = df['new_trip'].cumsum()
    d = ((df.x - df.x.shift()) ** 2 + (df.y - df.y.shift()) ** 2).pow(.5).fillna(0)
    df['distance'] = d

    # Filter out everything after the latest "not moving" event,
    # because a trip might still be ongoing
    if not include_all:
        not_moving = df[df.is_moving == False]
        if not len(not_moving):
            # If we don't have any "not moving" samples, just filter
            # out the last burst.
            df = df[df.created_at < df.created_at.max()]
        else:
            last_not_moving = not_moving.time.max()
            df = df[df.time <= last_not_moving]

    # Filter out trips that do not have enough low location error samples
    # far enough from the trip center point.
    good_samples = df[df.loc_error < 100]
    if not len(good_samples):
        print('No good samples, returning')
        return

    avg_loc = good_samples.groupby('trip_id')[['x', 'y']].mean()
    avg_loc.columns = ['avg_x', 'avg_y']
    d = good_samples.join(avg_loc, on='trip_id')
    d['mean_distance'] = ((d.x - d.avg_x) ** 2 + (d.y - d.avg_y) ** 2).pow(.5)

    loc_count = d[d['mean_distance'] > MIN_DISTANCE_MOVED_IN_TRIP].groupby('trip_id')['time'].count()
    trips_to_keep = loc_count.index[loc_count > 10]

    df.loc[~df.trip_id.isin(trips_to_keep), 'trip_id'] = -1

    if not include_all:
        df = df[df.trip_id >= 0]

    df = df.drop(columns=['timediff', 'new_trip'])
    pc.display('returning %d trips (%d rows)' % (len(trips_to_keep), len(df)))

    return df


ATYPE_MAPPING = {
    'still': 'still',
    'running': 'walking',
    'on_foot': 'walking',
    'walking': 'walking',
    'on_bicycle': 'cycling',
    'in_vehicle': 'driving',
    'unknown': None,
}
ATYPE_REVERSE = {
    'still': 'still',
    'walking': 'on_foot',
    'cycling': 'on_bicycle',
    'driving': 'in_vehicle',
}
ALL_ATYPES = [
    'still', 'on_foot', 'on_bicycle', 'in_vehicle', 'car', 'bus', 'tram', 'train', 'other', 'unknown',
]
ATYPE_STILL = ALL_ATYPES.index('still')
ATYPE_UNKNOWN = ALL_ATYPES.index('unknown')

IDX_MAPPING = {idx: ATYPE_REVERSE[x] for idx, x in enumerate(transport_modes.keys())}


def filter_trips(df: pd.DataFrame):
    out = df[['time', 'x', 'y', 'speed']].copy()
    s = df['time'].dt.tz_convert(None) - pd.Timestamp('1970-01-01')
    out['time'] = s / pd.Timedelta('1s')

    out['location_std'] = df['loc_error'].clip(lower=0.1)
    out['atype'] = df['atype'].map(ATYPE_MAPPING)
    out['aconf'] = df['aconf'] / 100
    out['vehicle_way_distance'] = df[['closest_car_way_dist', 'closest_rail_way_dist']].min(axis=1)
    out.loc[out.aconf == 1, 'aconf'] /= 2

    ms, Ss, state_probs, most_likely_path, _ = filter_trajectory((r for i, r in out.iterrows()))

    x = ms[:, 0]
    y = ms[:, 1]
    df = df.copy()
    df['xf'] = x
    df['yf'] = y
    df['atypef'] = most_likely_path
    df['atypef'] = df['atypef'].map(IDX_MAPPING)

    modes = transport_modes.keys()
    for idx, mode in enumerate(modes):
        if mode == 'driving':
            mode = 'in_vehicle'
        elif mode == 'cycling':
            mode = 'on_bicycle'
        df[mode] = [x[idx] for x in state_probs]

    return df


def read_uuids_from_sql(conn):
    print('Reading uids')
    with conn.cursor() as cursor:
        cursor.execute(f"""
            SELECT uuid, count(time) AS count FROM {TABLE_NAME}
                WHERE aconf IS NOT NULL AND time >= now() - interval '{DAYS_TO_FETCH} days'
                GROUP BY uuid
                ORDER BY count
                DESC LIMIT 1000
        """)
        rows = cursor.fetchall()
    uuid_counts = ['%s,%s' % (str(row[0]), row[1]) for row in rows]
    return uuid_counts


def read_uuids(conn):
    try:
        uuids = [x.split(',')[0].strip() for x in open('uuids.txt', 'r').readlines()]
    except FileNotFoundError:
        s = read_uuids_from_sql(conn)
        open('uuids.txt', 'w').write('\n'.join(s))
        uuids = [x.split(',')[0].strip() for x in s]
    return uuids


def get_transit_locations(conn, uid: str, start_time: datetime, end_time: datetime):
    query = """
        SELECT
            vehicle_journey_ref,
            vehicle_ref,
            time,
            extract(epoch from time) AS epoch_time,
            ST_X(loc) AS x,
            ST_Y(loc) AS y,
            route_type,
            (SELECT route_long_name FROM gtfs.routes
                WHERE feed_index = vl.gtfs_feed_id AND route_id = vl.gtfs_route_id
            ) AS route_name
        FROM transitrt_vehiclelocation vl
        WHERE
            time >= %(start)s :: timestamp - interval '1 minute' AND time <= %(end)s :: timestamp + interval '1 minute'
            AND loc && (
                SELECT ST_Buffer(ST_MakeLine(l.loc ORDER BY l.time), 200)
                FROM trips_ingest_location AS l
                WHERE
                    time >= %(start)s :: timestamp
                    AND time <= %(end)s :: timestamp
                    AND uuid = %(uuid)s
                    AND loc_error <= 200
            )
        ORDER BY time
    """
    params = dict(start=start_time, end=end_time, uuid=uid)

    df = pd.read_sql_query(query, conn, params=params)
    return df


@numba.njit(cache=True)
def filter_legs(time, x, y, atype, distance, loc_error, speed):
    n_rows = len(time)

    last_atype_start = 0
    atype_count = 0
    atype_counts = np.zeros(n_rows, dtype='int64')
    leg_ids = np.zeros(n_rows, dtype='int64')

    # First calculate how long same atype stretches we have
    for i in range(1, n_rows):
        if atype[i] == atype[i - 1] and i < n_rows - 1:
            if loc_error[i] < 100:
                atype_count += 1
        else:
            for j in range(last_atype_start, i):
                atype_counts[j] = atype_count
            atype_count = 0
            last_atype_start = i

    max_leg_id = 0
    current_leg = -1
    prev = 0
    for i in range(n_rows):
        # If we're in the middle of a trip and we have only a couple of atypes
        # for a different mode, change them to match the others.
        if i > 0 and i < n_rows - MIN_SAMPLES_PER_LEG:
            if atype_counts[i] <= 3 and atype_counts[i - 1] > MIN_SAMPLES_PER_LEG:
                atype[i] = atype[i - 1]
                atype_counts[i] = atype_counts[i - 1]

        if i == 0 or atype[i] != atype[i - 1]:
            if atype_counts[i] >= MIN_SAMPLES_PER_LEG and atype[i] != ATYPE_STILL and atype[i] != ATYPE_UNKNOWN:
                # Enough good samples in this leg? We'll keep it.
                if i > 0:
                    max_leg_id += 1
                current_leg = max_leg_id
                distance[i] = 0
                prev = i
            else:
                # Not enough? Amputation.
                current_leg = -1
            leg_ids[i] = current_leg
            continue
        elif current_leg == -1 or loc_error[i] > 100 or atype[i] == ATYPE_STILL or atype[i] == ATYPE_UNKNOWN:
            leg_ids[i] = -1
            continue

        dist = ((x[prev] - x[i]) ** 2 + (y[prev] - y[i]) ** 2) ** 0.5
        timediff = time[i] - time[prev]
        
        calc_speed = 0
        
        if timediff != 0:
            calc_speed = dist / timediff

        # If the speed based on (x, y) differs too much from speeds reported by GPS,
        # drop the previous sample as invalid.
        if not np.isnan(speed[i]) and abs(calc_speed - speed[i]) > 30:
            leg_ids[i - 1] = -1
            distance[i] = 0
        else:
            distance[i] = dist
        leg_ids[i] = current_leg
        prev = i

    return leg_ids


MAX_DISTANCE_BY_TRANSIT_TYPE = {
    0: 80,  # tram
    2: 500, # train
    3: 60,  # bus
}
ATYPE_BY_TRANSIT_TYPE = {
    0: 'tram',
    2: 'train',
    3: 'bus',
}


def split_trip_legs(conn, uid, df, include_all=False):
    assert len(df.trip_id.unique()) == 1

    s = df['time'].dt.tz_convert(None) - pd.Timestamp('1970-01-01')
    df['epoch_ts'] = s / pd.Timedelta('1s')
    df['calc_speed'] = df.speed
    df['int_atype'] = df.atype.map(ALL_ATYPES.index).astype(int)
    df['leg_id'] = filter_legs(
        time=df.epoch_ts.to_numpy(), x=df.x.to_numpy(), y=df.y.to_numpy(), atype=df.int_atype.to_numpy(),
        distance=df.distance.to_numpy(), loc_error=df.loc_error.to_numpy(), speed=df.speed.to_numpy(dtype=np.float64, na_value=np.nan)
    )
    df.atype = df.int_atype.map(lambda x: ALL_ATYPES[x])

    if False:
        pd.set_option("max_rows", None)
        pd.set_option("min_rows", None)
        print(df.set_index(df.time.dt.tz_convert(LOCAL_TZ)).drop(columns=['time']))

    if not include_all:
        df = df[df.leg_id != -1]
    if not len(df):
        return None

    df = df.copy()

    for leg_id in df.leg_id.unique():
        leg_df = df[df.leg_id == leg_id].copy()
        if leg_df.iloc[0].atype != 'in_vehicle':
            continue

        try:
            transit_locs = get_transit_locations(conn, uid, leg_df.time.min(), leg_df.time.max())
        except pd.io.sql.DatabaseError as e:
            logger.error('Error when querying transit locations from the db.', exc_info=e)
            continue
        if not len(transit_locs):
            continue
        transit_locs['time'] = transit_locs.epoch_time
        leg_df['location_std'] = leg_df['loc_error']
        transit_loc_by_id = {vech: d for vech, d in transit_locs.groupby('vehicle_ref')}
        transit_type_by_id = {vech: d.iloc[0].route_type for vech, d in transit_loc_by_id.items()}

        leg_df['time'] = df['epoch_ts'].astype(float)
        transit_probs = transit_prob_ests_糞(leg_df, transit_loc_by_id)
        transit_probs = sorted(
            [(key, dist) for key, dist in transit_probs.items() if dist == dist],
            key=lambda p: p[1]
        )
        if not len(transit_probs):
            continue
        vid, closest_dist = transit_probs[-1]
        vtype = transit_type_by_id[vid]
        max_dist = MAX_DISTANCE_BY_TRANSIT_TYPE.get(vtype, 30)

        if closest_dist > -max_dist:
            df.loc[df.leg_id == leg_id, 'atype'] = ATYPE_BY_TRANSIT_TYPE[vtype]

    df = df.drop(columns=['epoch_ts', 'calc_speed', 'int_atype'])

    return df


if __name__ == '__main__':
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine
    load_dotenv()
    eng = create_engine(os.getenv('DATABASE_URL'), echo=True)
    default_uid = os.getenv('DEFAULT_UUID')

    if False:
        start = datetime(2021, 4, 28, 12)
        end = start + timedelta(hours=1)
        out = get_vehicle_locations(eng, start, end)
        exit()

    if True:
        from dateutil.parser import parse
        pd.set_option("max_rows", None)
        pd.set_option("min_rows", None)
        df = read_locations(
            eng.connect().connection, default_uid,
            start_time='2021-05-12',
        )
        exit()
        trip_ids = df.trip_id.unique()
        for trip in trip_ids:
            print(trip)
            tdf = filter_trips(df[df.trip_id == trip])

    if True:
        for uid in read_uuids(eng):
            df = read_locations(eng, uid)
            print(df)
            exit()
    # split_trip_legs(df)
