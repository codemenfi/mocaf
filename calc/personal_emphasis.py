import typing

from django.contrib.gis.geos import Point
from django.db.models import Count, QuerySet
from django.contrib.gis.measure import D

from trips.models import Leg, TransportMode

mode_to_atype = {
    "walk": ["walking", "on_foot", "running"],
    "bicycle": ["on_bicycle"],
    "car": ["in_vehicle"],
    "bus": ["bus"],
    "tram": ["tram"],
    "train": ["train"],
    "still": ["still"],
    "other": ["other"]
}

atype_to_traj = {
    "walking": 1,
    "on_foot": 1,
    "running": 1,
    "on_bicycle": 2,
    "in_vehicle": 3,
    "bus": 3,
    "tram": 3,
    "train": 3,
    "still": 0,
    "other": 0
}

def transform_probs_to_trajectory_probs(probs: typing.Dict[str, float]) -> typing.List[float]:
    """
    Trajectory probs are a array of probabilities of being in each state.
    [still, walking, on_bicycle, in_vehicle]
    """

    grouped_propbs = [
        [], # still
        [], # walking
        [], # on_bicycle
        []  # in_vehicle
    ]
    print(probs)
    for key, value in probs.items():
        print(key, value)
        idx = atype_to_traj[key]
        grouped_propbs[idx].append(value)

    return [sum(group) / len(group) for group in grouped_propbs]




def similar_legs_by_location(device_id: int, start_loc: Point, end_loc: Point) -> QuerySet[Leg]:
    """
    Find legs that are similar to the given start and end locations.
    """
    return Leg.objects.filter(trip__device__pk=device_id, start_loc__distance_lte=D(start_loc, m=100), end_log__distance_lte=D(end_loc, m=100))


def similar_legs_by_length(device_id: int, start_loc: Point, end_loc: Point) -> typing.List[Leg]:
    """
    Find legs that are similar to the given start and end locations.
    """
    ...

def user_mode_prob_ests(device_id: int) -> typing.Dict[str, float]:
    """
    Calculate the probability of each mode for the user.
    """
    legs = Leg.objects.filter(trip__device__pk=device_id)

    return calculate_mode_probs(legs)

def probs_for_similar_legs(device_id: int, start_loc: Point, end_loc: Point) -> typing.Dict:
    """
    Find legs that are similar to the given start and end locations and calculate the probability of each mode.
    """
    legs = similar_legs_by_location(device_id, start_loc, end_loc)

    return calculate_mode_probs(legs)


def calculate_mode_probs(legs: QuerySet[Leg]) -> typing.Dict:
    """
    Calculate the percentages of each mode for the given legs.
    """

    counts = legs.values("mode").order_by("mode").annotate(count=Count("id"))
    total = sum(count["count"] for count in counts)

    modes = TransportMode.objects.all()

    probs = {}
    for mode in modes:
        mode_prob = next((count["count"] / total for count in counts if count["mode"] == mode), 0)
        atypes = mode_to_atype[mode.identifier]
        for atype in atypes:
            probs[atype] = mode_prob

    return probs




