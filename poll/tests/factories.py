from django.utils.timezone import make_aware, utc
from factory import SubFactory
from factory.django import DjangoModelFactory
from datetime import datetime, date, timedelta
from freezegun import freeze_time
from django.utils import timezone


class SurveyInfoFactory(DjangoModelFactory):
    class Meta:
        model = "poll.SurveyInfo"

    start_day = date(2023, 7, 15)
    end_day = date(2023, 7, 18)
    days = 3
    max_back_question = 3
    description = "test Survey"
    id = 2


class QuestionsFactory(DjangoModelFactory):
    class Meta:
        model = "poll.Questions"

    question_data = {"x": 5, "y": 6}
    question_type = "background"
    is_use = True
    description = "questions for test survey"


class ParticipantsFactory(DjangoModelFactory):
    class Meta:
        model = "poll.Partisipants"

    device = SubFactory("trips.tests.factories.DeviceFactory")
    survey_info = SubFactory(SurveyInfoFactory)
    start_date = date(2023, 7, 15)
    end_date = date(2023, 7, 18)
    approved = False
    back_question_answers = {"x": 5, "y": 6}
    feeling_question_answers = {"x": 5, "y": 6}
    id = 2


class DayInfoFactory(DjangoModelFactory):
    class Meta:
        model = "poll.DayInfo"

    partisipant = SubFactory(ParticipantsFactory)
    date = date(2023, 7, 15)
    approved = False


class LotteryFactory(DjangoModelFactory):
    class Meta:
        model = "poll.Lottery"

    user_name = "testUser"
    user_email = "test@mail.com"


@freeze_time("2023-07-15")
class TripsFactory(DjangoModelFactory):
    class Meta:
        model = "poll.Trips"

    partisipant = SubFactory(ParticipantsFactory)
    start_time = make_aware(datetime(2023, 7, 15, 20, 59, 40), utc)
    end_time = make_aware(datetime(2023, 7, 15, 23, 59, 45), utc)
    original_trip = True
    deleted = False
    id = 1


@freeze_time("2023-07-15")
class LegsFactory(DjangoModelFactory):
    class Meta:
        model = "poll.Legs"

    trip = SubFactory(TripsFactory)
    start_time = make_aware(datetime(2023, 7, 15, 20, 59, 40), utc)
    end_time = make_aware(datetime(2023, 7, 15, 23, 59, 40), utc)
    trip_length = 1860.702302423133
    carbon_footprint = 9303.511512115665
    nr_passengers = 1
    transport_mode = "walking"
    original_leg = True
    deleted = False
    id = 1
