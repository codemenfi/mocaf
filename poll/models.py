from django.db import models
from enum import Enum
from django.db import transaction
from django.contrib.gis.db import models
from datetime import datetime, timedelta, date
import random
import logging
import pytz
from django.conf import settings
from django.utils import timezone
from django.db.models import Q

LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)


class Question_type_choice(Enum):
    background = "background"
    feeling = "feeling"
    somethingelse = "somethingelse"


# Deprecated
class Trip_purpose(Enum):
    tyo = "työ"
    opiskelu = "opiskelu"
    tyoasia = "työasia/opiskelu"
    vapaaaika = "vapaa-aika"
    ostos = "ostos"
    muu = "muu asiointi ja kyyditseminen"
    tyhja = "tyhja"


class Municipality_choice(Enum):
    Tampere = "Tampere"
    Kangasala = "Kangasala"
    Lempaala = "Lempäälä"
    Nokia = "Nokia"
    Orivesi = "Orivesi"
    Pirkkala = "Pirkkala"
    Vesilahti = "Vesilahti"
    Ylojarvi = "Ylöjärvi"
    muu = "muu Suomi"


class SurveyInfo(models.Model):
    start_day = models.DateField(null=False)
    end_day = models.DateField(null=False)
    days = models.IntegerField(null=False, default=3)
    max_back_question = models.IntegerField(null=False, default=3)
    description = models.TextField(null=True)

    def get_random_startDate(self):
        dt_now = date.today()
        useStartDate = self.start_day

        if dt_now > useStartDate:
            useStartDate = dt_now

        delta = timedelta(days=(self.days - 1))
        lastCalcDay = self.end_day - delta
        multiply = (lastCalcDay - useStartDate) * random.random()
        randomDate = useStartDate + multiply
        return randomDate


class Questions(models.Model):
    question_data = models.JSONField(null=True)
    question_type = models.CharField(
        max_length=15,
        default=Question_type_choice("background").value,
        choices=[(tag, tag.value) for tag in Question_type_choice],
    )
    is_use = models.BooleanField(default=True)
    description = models.TextField(null=True)

    survey_info = models.ForeignKey(
        "poll.SurveyInfo", on_delete=models.CASCADE, null=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="question_type",
                check=models.Q(question_type__in=Question_type_choice._member_map_),
            )
        ]


class Partisipants(models.Model):
    device = models.ForeignKey("trips.Device", on_delete=models.CASCADE, null=True)

    survey_info = models.ForeignKey(
        "poll.SurveyInfo", on_delete=models.CASCADE, null=True
    )

    start_date = models.DateField(null=False)
    end_date = models.DateField(null=True)
    registered_to_survey_at = models.DateTimeField(null=True)

    approved = models.BooleanField(null=False, default=False)

    #    back_question = models.ForeignKey(
    #        'poll.questions', on_delete=models.PROTECT, null=True, limit_choices_to={'question_type': 'backgroud'}, related_name='+'
    #    )

    back_question_answers = models.JSONField(null=True)

    #    feeling_question = models.ForeignKey(
    #        'poll.questions', on_delete=models.PROTECT, null=True, limit_choices_to={'question_type': 'feeling'}, related_name='+'
    #    )

    feeling_question_answers = models.JSONField(null=True)

    class Meta:
        unique_together = ("device", "survey_info")


class DayInfo(models.Model):
    partisipant = models.ForeignKey(
        "poll.Partisipants", on_delete=models.CASCADE, null=True
    )

    date = models.DateField(null=False)

    approved = models.BooleanField(null=False, default=False)


class Lottery(models.Model):
    user_name = models.TextField()
    user_email = models.EmailField()


TRAVEL_TO_WORK_TRIP = "travel_to_work_trip"
BUSINESS_TRIP = "business_trip"
SCHOOL_TRIP = "school_trip"
LEISURE_TRIP = "leisure_trip"
SHOPPING_TRIP = "shopping_trip"
AFFAIR_TRIP = "affair_trip"
PASSENGER_TRANSPORT_TRIP = "passenger_transport_trip"

TRIP_PURPOSE_CHOICES = (
    (TRAVEL_TO_WORK_TRIP, "Työmatka"),
    (BUSINESS_TRIP, "Työasiamatka"),
    (SCHOOL_TRIP, "Koulu- tai opiskelumatka"),
    (LEISURE_TRIP, "Vapaa-ajanmatka"),
    (SHOPPING_TRIP, "Ostosmatka"),
    (AFFAIR_TRIP, "Asiointimatka"),
    (PASSENGER_TRANSPORT_TRIP, "Kyyditseminen"),
    ("tyhja", "Tyhjä"),
)

MUNICIPALITY_CHOICES = (
    ("Tampere", "Tampere"),
    ("Kangasala", "Kangasala"),
    ("Lempäälä", "Lempäälä"),
    ("Nokia", "Nokia"),
    ("Orivesi", "Orivesi"),
    ("Pirkkala", "Pirkkala"),
    ("Vesilahti", "Vesilahti"),
    ("Ylöjärvi", "Ylöjärvi"),
    ("Muu", "Muu"),
)

MUNICIPALITY_OTHER = "Muu"


class Trips(models.Model):
    partisipant = models.ForeignKey(
        "poll.Partisipants", on_delete=models.CASCADE, null=True
    )

    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
    original_trip = models.BooleanField(null=True, default=True)
    deleted = models.BooleanField(null=True, default=False)

    purpose = models.CharField(
        max_length=24,
        default="tyhja",
        null=False,
        choices=TRIP_PURPOSE_CHOICES,
    )

    approved = models.BooleanField(null=False, default=False)

    start_municipality = models.CharField(
        max_length=20,
        default="Tampere",
        choices=MUNICIPALITY_CHOICES,
    )

    end_municipality = models.CharField(
        max_length=20,
        default="Tampere",
        choices=MUNICIPALITY_CHOICES,
    )

    def deleteTrip(self):
        if self.original_trip == True:
            self.deleted = True
            self.save()
        else:
            self.delete()

    def addTrip(
        self,
        partisipantObj,
        StartTime,
        EndTime,
        start_municipality,
        end_municipality,
        purpose="travel_to_work_trip",
        approved=False,
        original_trip=False,
    ):
        self.partisipant = partisipantObj
        self.start_time = StartTime
        self.end_time = EndTime
        self.original_trip = original_trip
        self.purpose = purpose
        self.start_municipality = start_municipality
        self.end_municipality = end_municipality
        self.approved = approved
        self.save()

    def getPurposeVal(self):
        return self.get_purpose_display()

    def getstartMunicipalityVal(self):
        return self.get_start_municipality_display()

    def getendMunicipalityVal(self):
        return self.get_end_municipality_display()

    def get_update_end_time(self):
        return self.start_time + timedelta(days=3)

    @property
    def length(self) -> float:
        length = 0
        for leg in self.legs_set.all():
            length += leg.trip_length
        return length

    def last_leg(self):
        return self.legs_set.order_by("-end_time").first()

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="purpose",
                check=models.Q(purpose__in=[t[0] for t in TRIP_PURPOSE_CHOICES]),
            ),
            # Contstraint for now because of unicode errors
            # models.CheckConstraint(
            #     name="startmunicipality",
            #     check=models.Q(start_municipality__in=[t[0] for t in MUNICIPALITY_CHOICES]),
            # ),
            # models.CheckConstraint(
            #     name="endmunicipality",
            #     check=models.Q(end_municipality__in=[t[0] for t in MUNICIPALITY_CHOICES]),
            # ),
        ]


class Legs(models.Model):
    trip = models.ForeignKey("poll.Trips", on_delete=models.CASCADE, null=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    trip_length = models.FloatField(null=True)

    carbon_footprint = models.FloatField(null=True)

    nr_passengers = models.IntegerField(null=True)

    transport_mode = models.CharField(max_length=20, null=True)

    start_loc = models.PointField(null=True, srid=4326)
    end_loc = models.PointField(null=True, srid=4326)

    original_leg = models.BooleanField(null=True, default=True)
    deleted = models.BooleanField(null=True, default=False)

    received_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def deleteLeg(self):
        if self.original_leg == True:
            self.deleted = True
            self.save()
        else:
            self.delete()

        return True

    def can_user_update(self) -> bool:
        return timezone.now() < self.trip.get_update_end_time()


    def __str__(self):
        duration = (self.end_time - self.start_time).total_seconds() / 60
        deleted = 'DELETED ' if self.deleted else ''
        mode_str = self.transport_mode

        start_time = self.start_time.astimezone(LOCAL_TZ)

        return '%sLeg [%s]: Started at %s (duration %.1f min), length %.1f km' % (
            deleted, mode_str, start_time, duration, self.trip_length / 1000
        )

class LegsLocationQuerySet(models.QuerySet):
    def _get_expired_query(self):
        now = timezone.now()
        expiry_time = now - timedelta(hours=settings.ALLOWED_TRIP_UPDATE_HOURS)
        qs = Q(leg__start_time__lte=expiry_time)
        return qs

    def expired(self):
        return self.filter(self._get_expired_query())

    def active(self):
        return self.exclude(self._get_expired_query())


class LegsLocation(models.Model):
    leg = models.ForeignKey(Legs, on_delete=models.CASCADE, related_name="locations")
    loc = models.PointField(null=False, srid=4326)
    time = models.DateTimeField()
    speed = models.FloatField(null=True)

    objects = LegsLocationQuerySet.as_manager()

    class Meta:
        ordering = ("leg", "time")

    def __str__(self):
        time = self.time.astimezone(LOCAL_TZ)
        return "%s: %s (%.1f km/h)" % (time, self.loc, self.speed * 3.6)
