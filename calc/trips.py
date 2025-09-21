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


def filter_trips(df: pd.DataFrame, initial_state_prob_ests=None):
    out = df[['time', 'x', 'y', 'speed']].copy()
    s = df['time'].dt.tz_convert(None) - pd.Timestamp('1970-01-01')
    out['time'] = s / pd.Timedelta('1s')

    out['location_std'] = df['loc_error'].clip(lower=0.1)
    out['atype'] = df['atype'].map(ATYPE_MAPPING)
    out['aconf'] = df['aconf'] / 100
    out['vehicle_way_distance'] = df[['closest_car_way_dist', 'closest_rail_way_dist']].min(axis=1)
    out.loc[out.aconf == 1, 'aconf'] /= 2

    ms, Ss, state_probs, most_likely_path, _ = filter_trajectory((r for i, r in out.iterrows()), initial_state_prob_ests)

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


def get_dominant_mode_numpy(leg_ids, atype_array, leg_id):
    """Get the most frequent transport mode for a given leg."""
    mask = leg_ids == leg_id
    if not np.any(mask):
        return ATYPE_UNKNOWN
    
    leg_modes = atype_array[mask]
    if len(leg_modes) == 0:
        return ATYPE_UNKNOWN
    
    # Count occurrences of each mode
    unique_modes = np.unique(leg_modes)
    max_count = 0
    dominant_mode = ATYPE_UNKNOWN
    
    for mode in unique_modes:
        count = np.sum(leg_modes == mode)
        if count > max_count:
            max_count = count
            dominant_mode = mode
    
    return dominant_mode


def detect_and_merge_invalid_transitions(leg_ids, atype_array, time_array):
    """Detect and merge bicycle ↔ vehicle transitions without 'still' between them."""
    bicycle_mode = ALL_ATYPES.index('on_bicycle')
    vehicle_mode = ALL_ATYPES.index('in_vehicle')
    still_mode = ATYPE_STILL
    
    # Get unique leg IDs with their first occurrence times
    unique_legs = []
    leg_start_times = {}
    
    for i in range(len(leg_ids)):
        if leg_ids[i] != -1 and leg_ids[i] not in unique_legs:
            unique_legs.append(leg_ids[i])
            leg_start_times[leg_ids[i]] = time_array[i]
    
    if len(unique_legs) <= 1:
        return leg_ids
    
    # Sort legs by their start times
    sorted_legs = sorted(unique_legs, key=lambda x: leg_start_times[x])
    
    # Find invalid transitions
    legs_to_merge = []
    
    for i in range(len(sorted_legs) - 1):
        current_leg = sorted_legs[i]
        next_leg = sorted_legs[i + 1]
        
        current_mode = get_dominant_mode_numpy(leg_ids, atype_array, current_leg)
        next_mode = get_dominant_mode_numpy(leg_ids, atype_array, next_leg)
        
        # Check for invalid bicycle ↔ vehicle transition
        is_bicycle_to_vehicle = (current_mode == bicycle_mode and next_mode == vehicle_mode)
        is_vehicle_to_bicycle = (current_mode == vehicle_mode and next_mode == bicycle_mode)
        
        if is_bicycle_to_vehicle or is_vehicle_to_bicycle:
            # Find time range between legs
            current_end_time = np.max(time_array[leg_ids == current_leg])
            next_start_time = np.min(time_array[leg_ids == next_leg])
            
            # Check if there's enough 'still' time between legs
            between_mask = (time_array > current_end_time) & (time_array < next_start_time)
            still_between = np.sum((atype_array[between_mask] == still_mode) & (leg_ids[between_mask] == -1))
            
            # Require at least some 'still' samples between bicycle and vehicle (threshold: 3 samples)
            if still_between < 3:
                legs_to_merge.append((current_leg, next_leg))
    
    # Merge invalid transition legs
    for leg1, leg2 in legs_to_merge:
        # Count samples in each leg
        leg1_count = np.sum(leg_ids == leg1)
        leg2_count = np.sum(leg_ids == leg2)
        
        # Determine which leg to keep and which mode to use
        if leg1_count >= leg2_count:
            dominant_leg = leg1
            merge_target_mode = get_dominant_mode_numpy(leg_ids, atype_array, leg1)
        else:
            dominant_leg = leg2
            merge_target_mode = get_dominant_mode_numpy(leg_ids, atype_array, leg2)
        
        # Merge both legs under the same leg_id and transport mode
        merge_mask = (leg_ids == leg1) | (leg_ids == leg2)
        leg_ids[merge_mask] = dominant_leg
        atype_array[merge_mask] = merge_target_mode
    
    return leg_ids


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

# Define meaningful transport modes (excluding 'still' and 'unknown')
MEANINGFUL_TRANSPORT_MODES = ['walking', 'on_foot', 'on_bicycle', 'in_vehicle', 'car', 'bus', 'tram', 'train', 'other']

# Define transport mode similarity groups for merging
TRANSPORT_MODE_GROUPS = {
    'walking': ['walking', 'on_foot'],
    'cycling': ['on_bicycle'],
    'driving': ['in_vehicle', 'car'],
    'transit': ['bus', 'tram', 'train'],
    'other': ['other']
}


def get_transport_mode_group(mode):
    """Get the transport mode group for a given mode."""
    for group, modes in TRANSPORT_MODE_GROUPS.items():
        if mode in modes:
            return group
    return 'other'


def limit_transportation_methods(df, max_methods=3):
    """
    Limit a trip to maximum 3 transportation method changes.
    Merges similar or less confident segments to achieve this limit.
    
    Args:
        df: DataFrame with leg_id and atype columns
        max_methods: Maximum number of distinct transport methods allowed
    
    Returns:
        DataFrame with potentially modified atype values
    """
    if len(df) == 0:
        return df
    
    df = df.copy()
    
    # Get only meaningful transport modes (exclude still/unknown)
    meaningful_mask = df.atype.isin(MEANINGFUL_TRANSPORT_MODES) & (df.leg_id != -1)
    
    if not meaningful_mask.any():
        return df
    
    # Work with meaningful rows and create transport groups
    meaningful_df = df[meaningful_mask].copy()
    meaningful_df['transport_group'] = meaningful_df.atype.apply(get_transport_mode_group)
    
    # Create segments based on consecutive transport groups
    meaningful_df['group_change'] = meaningful_df.transport_group != meaningful_df.transport_group.shift()
    meaningful_df['segment_id'] = meaningful_df.group_change.cumsum()
    
    # Analyze segments
    segments = meaningful_df.groupby('segment_id').agg({
        'transport_group': 'first',
        'atype': lambda x: x.value_counts().index[0],  # Most frequent atype
        'time': ['min', 'max'],
        'leg_id': ['count', 'first', 'last']
    }).reset_index()
    
    # Flatten column names
    segments.columns = ['segment_id', 'transport_group', 'dominant_atype', 
                       'start_time', 'end_time', 'sample_count', 'first_leg', 'last_leg']
    segments['duration'] = (segments.end_time - segments.start_time).dt.total_seconds()
    
    unique_groups = segments.transport_group.nunique()
    
    # If we already have <= max_methods, return as-is
    if unique_groups <= max_methods:
        return df
    
    # Create a simpler merging strategy
    # Step 1: Merge shortest segments with adjacent segments
    while segments.transport_group.nunique() > max_methods and len(segments) > 1:
        # Find shortest segment
        shortest_idx = segments.duration.idxmin()
        shortest_segment = segments.loc[shortest_idx]
        
        # Determine which adjacent segment to merge with
        merge_target = None
        
        if shortest_idx > 0 and shortest_idx < len(segments) - 1:
            # Has both neighbors - choose the one with same group or longer duration
            prev_segment = segments.loc[shortest_idx - 1]
            next_segment = segments.loc[shortest_idx + 1]
            
            if prev_segment.transport_group == shortest_segment.transport_group:
                merge_target = shortest_idx - 1
            elif next_segment.transport_group == shortest_segment.transport_group:
                merge_target = shortest_idx + 1
            elif prev_segment.duration >= next_segment.duration:
                merge_target = shortest_idx - 1
            else:
                merge_target = shortest_idx + 1
                
        elif shortest_idx > 0:
            # Only has previous neighbor
            merge_target = shortest_idx - 1
        elif shortest_idx < len(segments) - 1:
            # Only has next neighbor
            merge_target = shortest_idx + 1
        else:
            # Only one segment left - can't merge
            break
        
        if merge_target is not None:
            target_segment = segments.loc[merge_target]
            
            # Merge segments - keep the transport group of the longer segment
            if shortest_segment.sample_count > target_segment.sample_count:
                # Shortest is actually longer, keep its attributes
                merged_group = shortest_segment.transport_group
                merged_atype = shortest_segment.dominant_atype
            else:
                # Target is longer, keep its attributes
                merged_group = target_segment.transport_group
                merged_atype = target_segment.dominant_atype
            
            # Update target segment with merged data
            segments.loc[merge_target, 'end_time'] = max(shortest_segment.end_time, target_segment.end_time)
            segments.loc[merge_target, 'start_time'] = min(shortest_segment.start_time, target_segment.start_time)
            segments.loc[merge_target, 'duration'] = (segments.loc[merge_target, 'end_time'] - 
                                                    segments.loc[merge_target, 'start_time']).total_seconds()
            segments.loc[merge_target, 'sample_count'] += shortest_segment.sample_count
            segments.loc[merge_target, 'transport_group'] = merged_group
            segments.loc[merge_target, 'dominant_atype'] = merged_atype
            
            # Mark shortest segment's rows for merging
            segment_mask = meaningful_df.segment_id == shortest_segment.segment_id
            meaningful_df.loc[segment_mask, 'segment_id'] = target_segment.segment_id
            
            # Remove shortest segment from segments list
            segments = segments.drop(shortest_idx).reset_index(drop=True)
    
    # Apply changes back to original dataframe
    # Create mapping from segment_id to new atype
    segment_atype_map = dict(zip(segments.segment_id, segments.dominant_atype))
    
    # Update meaningful rows with new atypes
    for idx, row in meaningful_df.iterrows():
        new_atype = segment_atype_map.get(row.segment_id)
        if new_atype and new_atype != row.atype:
            df.loc[idx, 'atype'] = new_atype
    
    return df


def split_trip_legs(conn, uid, df, include_all=False, user_has_car=True, limit_methods=False):
    assert len(df.trip_id.unique()) == 1

    s = df['time'].dt.tz_convert(None) - pd.Timestamp('1970-01-01')
    df['epoch_ts'] = s / pd.Timedelta('1s')
    df['calc_speed'] = df.speed
    df['int_atype'] = df.atype.map(ALL_ATYPES.index).astype(int)
    df['leg_id'] = filter_legs(
        time=df.epoch_ts.to_numpy(), x=df.x.to_numpy(), y=df.y.to_numpy(), atype=df.int_atype.to_numpy(),
        distance=df.distance.to_numpy(), loc_error=df.loc_error.to_numpy(), speed=df.speed.to_numpy(dtype=np.float64, na_value=np.nan)
    )
    
    # Apply invalid transition merging after filter_legs
    df['leg_id'] = detect_and_merge_invalid_transitions(
        df['leg_id'].to_numpy(), df.int_atype.to_numpy(), df.epoch_ts.to_numpy()
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

        # If we have a car, we'll only trust the transit location if it's very close.
        if closest_dist > -max_dist or not user_has_car:
            df.loc[df.leg_id == leg_id, 'atype'] = ATYPE_BY_TRANSIT_TYPE[vtype]

    df = df.drop(columns=['epoch_ts', 'calc_speed', 'int_atype'])
    
    # Limit the trip to maximum 3 transportation methods
    if limit_methods:
        df = limit_transportation_methods(df, max_methods=3)

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
