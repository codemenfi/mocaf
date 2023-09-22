import graphene
import pytz


from mocaf.graphql_types import AuthenticatedDeviceNode
from graphene_django import DjangoObjectType
from .models import *
from datetime import date, timedelta
from graphql.error import GraphQLError
from mocaf.graphql_types import AuthenticatedDeviceNode, DjangoNode
from mocaf.graphql_gis import LineStringScalar, PointScalar
from django.db import transaction, DatabaseError
from django.db.models import Q
import json
from types import SimpleNamespace

LOCAL_TZ = pytz.timezone("Europe/Helsinki")


class PollLegNode(DjangoNode, AuthenticatedDeviceNode):
    can_update = graphene.Boolean()
    geometry = LineStringScalar()

    def resolve_can_update(root: Legs, info):
        return root.can_user_update()

    def resolve_geometry(root: Legs, info):
        if not root.can_user_update():
            points = []
        else:
            points = list(
                root.locations.active().values_list("loc", flat=True).order_by("time")
            )
        return LineString(points)

    def resolve_locations(root: Legs, info):
        if not root.can_user_update():
            points = []
        else:
            points = root.locations.active()
        return points

    class Meta:
        model = Legs
        fields = [
            "id",
            "trip",
            "start_time",
            "end_time",
            "trip_length",
            "nr_passengers",
            "transport_mode",
            "start_loc",
            "end_loc",
            "original_leg",
            "deleted",
            "can_update",
            "geometry",
        ]


class TripNode(DjangoNode, AuthenticatedDeviceNode):
    legs = graphene.List(
        PollLegNode,
        offset=graphene.Int(),
        limit=graphene.Int(),
        order_by=graphene.String(),
    )
    start_time = graphene.DateTime()
    end_time = graphene.DateTime()
    length = graphene.Float()

    class Meta:
        model = Trips
        fields = [
            "id",
            "legs",
            "partisipant",
            "start_time",
            "end_time",
            "original_trip",
            "deleted",
            "purpose",
            "approved",
            "start_municipality",
            "end_municipality",
        ]


class PointModelType(graphene.ObjectType):
    location = graphene.Field(graphene.String, to=PointScalar())


class AddSurvey(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        start_day = graphene.Date(required=True)
        end_day = graphene.Date(required=True)
        days = graphene.Int(required=True)
        max_back_question = graphene.Int(required=False, default_value="")
        description = graphene.String(required=False, default_value="")

    ok = graphene.Boolean()

    @classmethod
    def mutate(
        cls, root, info, start_day, end_day, days, max_back_question="", description=""
    ):
        if start_day > (end_day - timedelta(days=(days - 1))):
            raise GraphQLError("Times are bad", [info])

        dayObjChk = SurveyInfo.objects.filter(
            start_day__gt=start_day, start_day__lt=end_day
        )
        dayObjChk2 = SurveyInfo.objects.filter(
            end_day__gte=start_day, end_day__lte=end_day
        )
        dayObjChk3 = SurveyInfo.objects.filter(
            start_day__lte=start_day, end_day__gte=end_day
        )

        if dayObjChk or dayObjChk2 or dayObjChk3:
            raise GraphQLError("There is allready survey on that time", [info])

        obj = SurveyInfo()

        obj.days = days
        obj.start_day = start_day
        obj.end_day = end_day

        if max_back_question != "":
            obj.max_back_question = max_back_question

        if description != "":
            obj.description = description

        obj.save()

        return dict(ok=True)


class ApproveUserSurvey(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        surveyId = graphene.ID(required=False)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, surveyId):
        okVal = True
        device = info.context.device
        partisipantObj = Partisipants.objects.get(survey_info=surveyId, device=device)

        daysObj = DayInfo.objects.filter(partisipant=partisipantObj, approved=False)

        if daysObj:
            okVal = True
            raise GraphQLError("There are non approved days", [info])

        partisipantObj.approved = True
        partisipantObj.save()

        return dict(ok=okVal)


class EnrollLottery(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, name, email):
        obj = Lottery()

        obj.user_name = name
        obj.user_email = email

        obj.save()

        return dict(ok=True)


class EnrollToSurvey(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        surveyId = graphene.ID(required=False)
        back_question_answers = graphene.String(required=False, default_value="")
        feeling_question_answers = graphene.String(required=False, default_value="")

    ok = graphene.Boolean()

    @classmethod
    def mutate(
        cls, root, info, surveyId, back_question_answers="", feeling_question_answers=""
    ):
        okVal = True
        device = info.context.device

        partObjChk = Partisipants.objects.filter(survey_info=surveyId, device=device)

        if partObjChk:
            raise GraphQLError("User has allready enrolled to survey", [info])

        try:
            with transaction.atomic():
                obj = Partisipants()
                obj.device = info.context.device
                obj.survey_info = SurveyInfo.objects.get(pk=surveyId)
                dev = info.context.device
                if back_question_answers != "":
                    obj.back_question_answers = back_question_answers

                if feeling_question_answers != "":
                    obj.feeling_question_answers = feeling_question_answers

                obj.start_date = date.today()
                obj.registered_to_survey_at = timezone.now()
                dev.survey_enabled = True
                dev.save()
                obj.save()

                surveyStartDate = obj.survey_info.get_random_startDate()

                obj.start_date = surveyStartDate

                for x in range(0, obj.survey_info.days):
                    dayInfoObj = DayInfo()
                    dayInfoObj.partisipant = obj
                    dayInfoObj.date = surveyStartDate
                    dayInfoObj.save()
                    surveyStartDate = surveyStartDate + timedelta(days=1)

                surveyStartDate = surveyStartDate - timedelta(days=1)

                obj.end_date = surveyStartDate

                obj.save()

        except DatabaseError:
            okVal = False

        return dict(ok=okVal)


class AddUserAnswerToQuestions(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        surveyId = graphene.ID(required=True)
        back_question_answers = graphene.String(required=False, default_value="")
        feeling_question_answers = graphene.String(required=False, default_value="")

    ok = graphene.Boolean()

    @classmethod
    def mutate(
        cls, root, info, surveyId, back_question_answers="", feeling_question_answers=""
    ):
        device = info.context.device
        obj = Partisipants.objects.get(survey_info=surveyId, device=device)

        if back_question_answers != "":
            obj.back_question_answers = back_question_answers

        if feeling_question_answers != "":
            obj.feeling_question_answers = feeling_question_answers

        obj.save()

        return dict(ok=True)


class AddQuestion(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        question = graphene.String(required=True)
        questionType = graphene.String(
            required=True, description="background, feeling, somethingelse"
        )
        description = graphene.String(required=True)
        surveyId = graphene.ID(required=False, default_value="")

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, question, questionType, description, surveyId=""):
        obj = Questions()
        obj.question_data = question
        obj.question_type = questionType
        obj.description = description

        if surveyId != "":
            surveyInfoObj = SurveyInfo.objects.get(pk=surveyId)
            obj.survey_info = surveyInfoObj

        obj.save()

        return dict(ok=True)


class MarkUserDayReady(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        selectedDate = graphene.Date(required=True)
        surveyId = graphene.ID(required=True)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, selectedDate, surveyId):
        device = info.context.device

        partisipantObj = Partisipants.objects.get(survey_info=surveyId, device=device)

        tripsObj = Trips.objects.filter(
            partisipant=partisipantObj, start_time__date=selectedDate, deleted=False
        )

        for trip in tripsObj:
            if trip.purpose == "":
                raise GraphQLError("All date trip needs purpose", [info])

            if trip.approved == False:
                legsObj = Legs.objects.filter(trip=trip)
                if not legsObj:
                    raise GraphQLError("Trip has no legs", [info])

                trip.approved = True
                trip.save()

        dayInfoObj = DayInfo.objects.get(date=selectedDate, partisipant=partisipantObj)
        dayInfoObj.approved = True

        dayInfoObj.save()

        return dict(ok=True)


class AddTrip(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        start_time = graphene.DateTime(required=True)
        end_time = graphene.DateTime(required=True)
        surveyId = graphene.ID(required=True)
        purpose = graphene.String(
            required=False,
            default_value="",
            description="tyo, opiskelu, tyoasia, vapaaaika, ostos, muu",
        )
        start_municipality = graphene.String(
            required=False,
            default_value="Tampere",
            description="Tampere, Kangasala, Lempäälä, Nokia, Orivesi, Pirkkala, Vesilahti, Ylöjärvi, Muu",
        )
        end_municipality = graphene.String(
            required=False,
            default_value="Tampere",
            description="Tampere, Kangasala, Lempäälä, Nokia, Orivesi, Pirkkala, Vesilahti, Ylöjärvi, Muu",
        )

    ok = graphene.ID()

    @classmethod
    def mutate(
        cls,
        root,
        info,
        start_time,
        end_time,
        surveyId,
        purpose,
        start_municipality,
        end_municipality,
    ):
        device = info.context.device
        partisipant = Partisipants.objects.get(survey_info=surveyId, device=device)

        if start_time == "":
            raise GraphQLError("Missing start time", [info])

        if end_time == "":
            raise GraphQLError("Missing end time", [info])

        start_time_d = LOCAL_TZ.localize(start_time, is_dst=None)
        start_time_tz = start_time_d.astimezone(pytz.utc)

        end_time_d = LOCAL_TZ.localize(end_time, is_dst=None)
        end_time_tz = end_time_d.astimezone(pytz.utc)

        if start_time >= end_time:
            raise GraphQLError("Start time is after end time", [info])

        overlapping_trips = Trips.objects.filter(
            Q(Q(start_time__gt=start_time_tz) & Q(start_time__lt=end_time_tz))
            | Q(Q(end_time__gt=start_time_tz) & Q(end_time__lt=end_time_tz))
            | Q(Q(start_time__lte=start_time_tz) & Q(end_time__gte=end_time_tz)),
            deleted=False,
            partisipant=partisipant,
        )

        if overlapping_trips:
            raise GraphQLError("Timespan overlaps with another trip", [info])

        survey_day = DayInfo.objects.filter(
            date=start_time_tz.date(), approved=False, partisipant=partisipant
        )

        if not survey_day:
            raise GraphQLError(
                "The trip is not set on a correct traffic survey date", [info]
            )

        dt_now = datetime.today()
        time_limit = end_time + timedelta(days=3)
        if dt_now > time_limit:
            raise GraphQLError("Dates can be edited only three days", [info])

        trip = Trips(
            partisipant=partisipant,
            start_time=start_time_tz,
            end_time=end_time_tz,
            start_municipality=start_municipality,
            end_municipality=end_municipality,
            purpose=purpose,
        )

        trip.save()

        return dict(ok=trip.pk)


class AddLeg(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_id = graphene.ID(required=True)
        trip_length = graphene.Float(required=False, default_value="")
        transport_mode = graphene.String(required=False, default_value="")
        nr_passengers = graphene.String(required=False, default_value="")
        start_loc = graphene.Argument(PointScalar, required=False, default_value="")
        end_loc = graphene.Argument(PointScalar, required=False, default_value="")

    ok = graphene.Boolean()

    @classmethod
    def mutate(
        cls,
        root,
        info,
        trip_id,
        trip_length="",
        transport_mode="",
        nr_passengers="",
        start_loc="",
        end_loc="",
    ):
        try:
            with transaction.atomic():
                trip = Trips.objects.get(pk=trip_id)

                if trip.approved == True:
                    raise GraphQLError("Trip has allready been approved", [info])
                elif trip.deleted == True:
                    raise GraphQLError("Trip has been deleted", [info])

                leg = Legs()
                leg.trip = trip

                # Set the start and end times automatically for now
                previous_leg = trip.last_leg()
                if previous_leg:
                    leg.start_time = previous_leg.end_time
                    leg.end_time = previous_leg.end_time + timedelta(minutes=1)
                else:
                    leg.start_time = trip.start_time
                    leg.end_time = trip.start_time + timedelta(minutes=1)

                if trip_length != "":
                    leg.trip_length = trip_length

                if transport_mode != "":
                    leg.transport_mode = transport_mode

                if nr_passengers != "":
                    leg.nr_passengers = nr_passengers

                leg.original_leg = False

                if start_loc != "":
                    leg.start_loc = PointModelType(start_loc)

                if end_loc != "":
                    leg.end_loc = PointModelType(end_loc)

                leg.save()

        except DatabaseError:
            return dict(ok=False)

        return dict(ok=True)


class EditLeg(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        leg_id = graphene.ID(required=True)
        trip_length = graphene.Float(required=False, default_value="")
        transport_mode = graphene.String(required=False, default_value="")
        nr_passengers = graphene.String(required=False, default_value="")
        start_loc = graphene.Argument(PointScalar, required=False, default_value="")
        end_loc = graphene.Argument(PointScalar, required=False, default_value="")

    ok = graphene.Boolean()
    leg = graphene.Field(PollLegNode)

    @classmethod
    def mutate(
        cls,
        root,
        info,
        leg_id,
        trip_length="",
        transport_mode="",
        nr_passengers="",
        start_loc="",
        end_loc="",
    ):
        try:
            leg = Legs.objects.get(pk=leg_id)
        except Legs.DoesNotExist:
            raise GraphQLError("Leg does not exist", [info])

        try:
            with transaction.atomic():
                if leg.trip.approved == True:
                    raise GraphQLError("Trip is allready approved", [info])
                elif leg.trip.deleted == True:
                    raise GraphQLError("Trip is deleted", [info])

                if trip_length != "":
                    leg.trip_length = trip_length

                if transport_mode != "":
                    leg.transport_mode = transport_mode

                if nr_passengers != "":
                    leg.nr_passengers = nr_passengers

                leg.original_leg = False

                if start_loc != "":
                    leg.start_loc = PointModelType(start_loc)

                if end_loc != "":
                    leg.end_loc = PointModelType(end_loc)

                leg.save()

        except DatabaseError:
            return dict(ok=False, leg=leg)

        return dict(ok=True, leg=leg)


class AddLegs(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_id = graphene.ID(required=True)
        data_json = graphene.JSONString(
            required=True,
            description='[{"startTime":"2023-07-13T20:59:40","endTime":"2023-07-13T23:59:45"},{"startTime":"2023-07-13T20:59:40","endTime":"2023-07-13T23:59:45"}] type json',
        )

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, trip_id, data_json):
        data_json_str = json.dumps(data_json)
        data_object = json.loads(data_json_str)

        date_format = "%Y-%m-%d" + "T" + "%H:%M:%S"

        for i in data_object:
            start_time = datetime.strptime(i.get("startTime"), date_format)
            end_time = datetime.strptime(i.get("endTime"), date_format)

            trip_length = ""
            transport_mode = ""
            nr_passengers = ""
            start_loc = ""
            end_loc = ""

            if i.get("tripLength"):
                trip_length = float(i.get("tripLength"))
            if i.get("transportMode"):
                transport_mode = i.get("transportMode")
            if i.get("nrPassengers"):
                nr_passengers = i.get("nrPassengers")
            if i.get("startLoc"):
                start_loc = i.get("startLoc")
            if i.get("endLoc"):
                end_loc = i.get("endLoc")

            start_time_d = LOCAL_TZ.localize(start_time, is_dst=None)
            end_time_d = LOCAL_TZ.localize(end_time, is_dst=None)
            fixStartTime = start_time_d.astimezone(pytz.utc)
            fixEndTime = end_time_d.astimezone(pytz.utc)

            dt_now = datetime.today()
            timetestVal = end_time + timedelta(days=3)
            if dt_now > timetestVal:
                raise GraphQLError("Dates can be edited only three days", [info])

            legObjChk = Legs.objects.filter(
                start_time__gt=fixStartTime,
                start_time__lt=fixEndTime,
                deleted=False,
                trip=trip_id,
            )
            legObjChk2 = Legs.objects.filter(
                end_time__gt=fixStartTime,
                end_time__lt=fixEndTime,
                deleted=False,
                trip=trip_id,
            )
            legObjChk3 = Legs.objects.filter(
                start_time__lte=fixStartTime,
                end_time__gte=fixEndTime,
                deleted=False,
                trip=trip_id,
            )

            if start_time >= end_time or legObjChk or legObjChk2 or legObjChk3:
                raise GraphQLError("Times are bad", [info])

            okVal = True

            try:
                with transaction.atomic():
                    tripObj = Trips.objects.get(pk=trip_id)

                    if tripObj.approved == True:
                        raise GraphQLError("Trip is allready approved", [info])
                    elif tripObj.deleted == True:
                        raise GraphQLError("Trip is deleted", [info])

                    dayChk = DayInfo.objects.filter(
                        date=fixStartTime.date(),
                        approved=False,
                        partisipant=tripObj.partisipant,
                    )

                    if not dayChk:
                        raise GraphQLError("Start day is bad", [info])

                    legsObj = Legs()

                    legsObj.trip = tripObj
                    legsObj.start_time = fixStartTime
                    legsObj.end_time = fixEndTime

                    if trip_length != "":
                        legsObj.trip_length = trip_length

                    if transport_mode != "":
                        legsObj.transport_mode = transport_mode

                    if nr_passengers != "":
                        legsObj.nr_passengers = nr_passengers

                    legsObj.original_leg = False

                    if start_loc != "":
                        legsObj.start_loc = PointModelType(start_loc)

                    if end_loc != "":
                        legsObj.end_loc = PointModelType(end_loc)

                    legsObj.save()

                    tripObjChange = False

                    if fixStartTime < tripObj.start_time:
                        tripObj.start_time = fixStartTime
                        tripObjChange = True

                    if fixEndTime > tripObj.end_time:
                        tripObj.end_time = fixEndTime
                        tripObjChange = True

                    if tripObjChange:
                        tripObj.save()

            except DatabaseError:
                okVal = False
                break

        return dict(ok=okVal)


class LocationToLeg(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        loc = graphene.Argument(PointScalar)
        leg_id = graphene.ID(required=True)
        time = graphene.DateTime(required=False, default_value="")

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, leg_id, loc, time=""):
        legsObj = Legs.objects.get(pk=leg_id)

        dt_now = datetime.today()
        timetestVal = time + timedelta(days=3)
        if dt_now > timetestVal:
            raise GraphQLError("Dates can be edited only three days", [info])

        if legsObj.start_time > time or time > legsObj.end_time:
            raise GraphQLError("Times are bad", [info])

        LogObj = LegsLocation()
        LogObj.leg = legsObj
        LogObj.loc = PointModelType(loc)

        if time != "":
            LogObj.time = time

        LogObj.save()

        return dict(ok=True)


class DelTrip(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_id = graphene.ID(required=True)
        surveyId = graphene.ID(required=True)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, trip_id, surveyId):
        device = info.context.device

        partisipantObj = Partisipants.objects.get(survey_info=surveyId, device=device)

        tripObj = Trips.objects.get(partisipant=partisipantObj, pk=trip_id)

        dt_now = LOCAL_TZ.localize(datetime.today())
        timetestVal = tripObj.end_time + timedelta(days=3)
        if dt_now > timetestVal:
            raise GraphQLError("Dates can be edited only three days", [info])

        if tripObj.approved == True:
            raise GraphQLError("Trip is allready approved", [info])

        tripObj.deleteTrip()

        return dict(ok=True)


class DelTrips(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_ids = graphene.List(graphene.Int, required=True, description="Trip ids")
        surveyId = graphene.ID(required=True)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, trip_ids, surveyId):
        for trip_id in trip_ids:
            device = info.context.device

            partisipantObj = Partisipants.objects.get(
                survey_info=surveyId, device=device
            )

            tripObj = Trips.objects.get(partisipant=partisipantObj, pk=trip_id)

            dt_now = LOCAL_TZ.localize(datetime.today())
            timetestVal = tripObj.end_time + timedelta(days=3)

            if dt_now > timetestVal:
                raise GraphQLError("Dates can be edited only three days", [info])

            if tripObj.approved == True:
                raise GraphQLError("Trip is allready approved", [info])

            tripObj.deleteTrip()

        return dict(ok=True)


class DelLeg(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_id = graphene.ID(required=True)
        leg_id = graphene.ID(required=True)
        surveyId = graphene.ID(required=True)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, trip_id, surveyId, leg_id):
        device = info.context.device
        okVal = True

        try:
            with transaction.atomic():
                partisipantObj = Partisipants.objects.get(
                    survey_info=surveyId, device=device
                )

                tripObj = Trips.objects.get(partisipant=partisipantObj, pk=trip_id)

                dt_now = LOCAL_TZ.localize(datetime.today())
                timetestVal = tripObj.end_time + timedelta(days=3)
                if dt_now > timetestVal:
                    raise GraphQLError("Dates can be edited only three days", [info])

                if tripObj.approved == True:
                    raise GraphQLError("Trip is allready approved", [info])

                legObj = Legs.objects.get(trip=tripObj, pk=leg_id)

                tripObjChange = False

                if tripObj.start_time == legObj.start_time:
                    tripObj.start_time = legObj.end_time
                    tripObjChange = True

                if tripObj.end_time == legObj.end_time:
                    tripObj.end_time = legObj.start_time
                    tripObjChange = True

                if tripObjChange:
                    tripObj.save()

                legObj.deleteLeg()

        except DatabaseError:
            okVal = False

        return dict(ok=okVal)


class JoinTrip(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_id = graphene.ID(required=True)
        trip2_id = graphene.ID(required=True)
        surveyId = graphene.ID(required=True)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, trip_id, trip2_id, surveyId):
        device = info.context.device

        okVal = True

        try:
            with transaction.atomic():
                partisipantObj = Partisipants.objects.get(
                    survey_info=surveyId, device=device
                )

                tripKeepObj = Trips.objects.get(partisipant=partisipantObj, pk=trip_id)
                tripRemoveObj = Trips.objects.get(
                    partisipant=partisipantObj, pk=trip2_id
                )

                dt_now = LOCAL_TZ.localize(datetime.today())
                timetestVal = tripRemoveObj.end_time + timedelta(days=3)
                if dt_now > timetestVal:
                    raise GraphQLError("Dates can be edited only three days", [info])

                if tripKeepObj.approved == True or tripRemoveObj.approved == True:
                    raise GraphQLError("Trip is allready approved", [info])
                elif tripKeepObj.deleted == True or tripRemoveObj.deleted == True:
                    raise GraphQLError("Trip is deleted", [info])

                tripObjChange = False

                if tripKeepObj.start_time > tripRemoveObj.start_time:
                    tripKeepObj.start_time = tripRemoveObj.start_time
                    tripObjChange = True

                if tripKeepObj.end_time < tripRemoveObj.end_time:
                    tripKeepObj.end_time = tripRemoveObj.end_time
                    tripObjChange = True

                if tripObjChange:
                    tripKeepObj.save()

                legsObj = Legs.objects.filter(trip=trip2_id)

                legsObj.update(trip=tripKeepObj)

                tripRemoveObj.deleteTrip()

        except DatabaseError:
            okVal = False

        return dict(ok=okVal)


class SplitTrip(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_id = graphene.ID(required=True)
        after_leg_id = graphene.ID(required=True)
        surveyId = graphene.ID(required=True)

    ok = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, trip_id, after_leg_id, surveyId):
        device = info.context.device
        okVal = True

        try:
            with transaction.atomic():
                partisipantObj = Partisipants.objects.get(
                    survey_info=surveyId, device=device
                )

                oldTripObj = Trips.objects.get(partisipant=partisipantObj, pk=trip_id)

                dt_now = LOCAL_TZ.localize(datetime.today())
                timetestVal = oldTripObj.end_time + timedelta(days=3)
                if dt_now > timetestVal:
                    raise GraphQLError("Dates can be edited only three days", [info])

                if oldTripObj.approved == True:
                    raise GraphQLError("Trip is allready approved", [info])
                elif oldTripObj.deleted == True:
                    raise GraphQLError("Trip is deleted", [info])

                lastLeg = Legs.objects.get(pk=after_leg_id)

                legsObj = Legs.objects.filter(
                    trip=trip_id, start_time__gte=lastLeg.start_time
                ).order_by("start_time")
                first = True
                newStartTime = lastLeg.start_time
                newEndTime = lastLeg.end_time

                if not legsObj:
                    raise GraphQLError("No legs after given leg", [info])

                for legs in legsObj:
                    if first == True:
                        first = False
                        newStartTime = legs.start_time

                    newEndTime = legs.end_time

                oldTripObj.end_time = lastLeg.end_time
                oldTripObj.save()

                tripObj = Trips()
                tripObj.partisipant = partisipantObj
                tripObj.start_time = newStartTime
                tripObj.end_time = newEndTime
                tripObj.original_trip = False

                tripObj.purpose = oldTripObj.purpose
                tripObj.start_municipality = oldTripObj.start_municipality
                tripObj.end_municipality = oldTripObj.end_municipality

                tripObj.save()

                legsObj.update(trip=tripObj)

        except DatabaseError:
            okVal = False

        return dict(ok=okVal)


class EditTrip(graphene.Mutation, AuthenticatedDeviceNode):
    class Arguments:
        trip_id = graphene.ID(required=True)
        start_time = graphene.DateTime(required=False, default_value="")
        end_time = graphene.DateTime(required=False, default_value="")
        surveyId = graphene.ID(required=True)
        purpose = graphene.String(
            required=False,
            default_value="",
            description="tyo, opiskelu, tyoasia, vapaaaika, ostos, muu",
        )
        start_municipality = graphene.String(
            required=False,
            default_value="",
            description="Tampere, Kangasala, Lempäälä, Nokia, Orivesi, Pirkkala, Vesilahti, Ylöjärvi, Muu",
        )
        end_municipality = graphene.String(
            required=False,
            default_value="",
            description="Tampere, Kangasala, Lempäälä, Nokia, Orivesi, Pirkkala, Vesilahti, Ylöjärvi, Muu",
        )
        approved = graphene.Boolean(required=False, default_value="")

    ok = graphene.Boolean()

    @classmethod
    def mutate(
        cls,
        root,
        info,
        trip_id,
        surveyId,
        start_time,
        end_time,
        purpose,
        start_municipality,
        end_municipality,
        approved,
    ):
        device = info.context.device

        partisipant = Partisipants.objects.get(survey_info=surveyId, device=device)

        if start_time == "":
            raise GraphQLError("Missing start time", [info])

        if end_time == "":
            raise GraphQLError("Missing end time", [info])

        start_time_d = LOCAL_TZ.localize(start_time, is_dst=None)
        start_time_tz = start_time_d.astimezone(pytz.utc)

        end_time_d = LOCAL_TZ.localize(end_time, is_dst=None)
        end_time_tz = end_time_d.astimezone(pytz.utc)

        if start_time >= end_time:
            raise GraphQLError("Start time is after end time", [info])

        overlapping_trips = Trips.objects.filter(
            ~Q(pk=trip_id),
            Q(Q(start_time__gt=start_time_tz) & Q(start_time__lt=end_time_tz))
            | Q(Q(end_time__gt=start_time_tz) & Q(end_time__lt=end_time_tz))
            | Q(Q(start_time__lte=start_time_tz) & Q(end_time__gte=end_time_tz)),
            deleted=False,
            partisipant=partisipant,
        )

        if overlapping_trips:
            raise GraphQLError("Timespan overlaps with another trip", [info])

        survey_day = DayInfo.objects.filter(
            date=start_time_tz.date(), approved=False, partisipant=partisipant
        )

        if not survey_day:
            raise GraphQLError(
                "The trip is not set on a correct traffic survey date", [info]
            )

        okVal = True

        trip = Trips.objects.get(partisipant=partisipant, pk=trip_id)

        dt_now = LOCAL_TZ.localize(datetime.today())
        timetestVal = trip.end_time + timedelta(days=3)
        if dt_now > timetestVal:
            raise GraphQLError("Dates can be edited only three days", [info])

        if approved != "" and approved == True:
            if trip.purpose == "" and purpose == "":
                raise GraphQLError("Trip needs purpose", [info])

            legs = Legs.objects.filter(trip=trip_id)
            if not legs:
                raise GraphQLError("Trip has no legs", [info])

        if (approved == "" or approved == True) and trip.approved == True:
            raise GraphQLError("Trip is already approved", [info])
        elif trip.deleted == True:
            raise GraphQLError("Trip is deleted", [info])

        if trip.original_trip == False or (start_time_tz == "" and end_time_tz == ""):
            if start_time_tz != "":
                trip.start_time = start_time_tz
            if end_time_tz != "":
                trip.end_time = end_time_tz
            if purpose != "":
                trip.purpose = purpose
            if start_municipality != "":
                trip.start_municipality = start_municipality
            if end_municipality != "":
                trip.end_municipality = end_municipality
            if approved != "":
                trip.approved = approved
            trip.save()
        else:
            new_trip = Trips()

            new_trip.original_trip = False
            new_trip.partisipant = trip.partisipant
            new_trip.start_time = trip.start_time
            new_trip.end_time = trip.end_time
            new_trip.purpose = trip.purpose
            new_trip.start_municipality = trip.start_municipality
            new_trip.end_municipality = trip.end_municipality

            if start_time_tz != "":
                new_trip.start_time = start_time_tz
            if end_time_tz != "":
                new_trip.end_time = end_time_tz
            if purpose != "":
                new_trip.purpose = purpose
            if start_municipality != "":
                new_trip.start_municipality = start_municipality
            if end_municipality != "":
                new_trip.end_municipality = end_municipality
            if approved != "":
                new_trip.approved = approved

            new_trip.save()

            legs = Legs.objects.filter(trip=trip_id)
            legs.update(trip=new_trip)
            trip.deleteTrip()

        return dict(ok=okVal)


class Mutations(graphene.ObjectType):
    pollEnrollToSurvey = EnrollToSurvey.Field()
    pollEnrollLottery = EnrollLottery.Field()
    pollAddSurvey = AddSurvey.Field()
    pollAddUserAnswerToQuestions = AddUserAnswerToQuestions.Field()
    pollAddQuestion = AddQuestion.Field()
    pollMarkUserDayReady = MarkUserDayReady.Field()
    pollAddTrip = AddTrip.Field()
    pollAddLeg = AddLeg.Field()
    pollAddLegs = AddLegs.Field()
    pollEditLeg = EditLeg.Field()
    pollDelTrip = DelTrip.Field()
    pollDelTrips = DelTrips.Field()
    pollDelLeg = DelLeg.Field()
    pollJoinTrip = JoinTrip.Field()
    pollSplitTrip = SplitTrip.Field()
    pollLocationToLeg = LocationToLeg.Field()
    pollEditTrip = EditTrip.Field()
    pollApproveUserSurvey = ApproveUserSurvey.Field()


class Survey(DjangoObjectType):
    class Meta:
        model = SurveyInfo
        field = ("start_day", "end_day", "days", "max_back_question", "description")


class UserSurvey(DjangoObjectType):
    class Meta:
        model = Partisipants
        field = (
            "start_date",
            "end_date",
            "back_question_answers",
            "feeling_question_answers",
            "approved",
        )


class surveyQuestions(DjangoObjectType):
    class Meta:
        model = Questions
        field = ("pk", "question_data", "question_type", "description", "survey_info")


class surveyQuestion(DjangoObjectType):
    class Meta:
        model = Questions
        field = ("pk", "question_data", "question_type", "description", "survey_info")


class dayTrips(DjangoObjectType):
    class Meta:
        model = Trips
        field = ("pk", "start_time", "end_time", "original_trip", "approved")
        exclude = ("purpose",)

    user_purpose = graphene.String()
    start_municipality = graphene.String()
    end_municipality = graphene.String()

    def resolve_user_purpose(self, info):
        return Trips.getPurposeVal(self)

    def resolve_start_municipality(self, info):
        return Trips.getstartMunicipalityVal(self)

    def resolve_end_municipality(self, info):
        return Trips.getendMunicipalityVal(self)


class tripsLegs(DjangoObjectType):
    class Meta:
        model = Legs
        field = (
            "pk",
            "start_time",
            "end_time",
            "original_leg",
            "trip_length",
            "transport_mode",
            "start_loc",
            "end_loc",
        )


class Query(graphene.ObjectType):
    pollActiveSurveyInfo = graphene.Field(Survey, selectedDate=graphene.Date())
    pollSurveyInfo = graphene.List(Survey)
    pollUserSurvey = graphene.List(UserSurvey, survey_id=graphene.Int())
    pollSurveyQuestions = graphene.List(
        surveyQuestions,
        question_type=graphene.String(description="background, feeling, somethingelse"),
        survey_id=graphene.Int(),
    )
    pollSurveyQuestion = graphene.List(surveyQuestion, question_id=graphene.Int())
    pollDayTrips = graphene.List(
        dayTrips, day=graphene.Date(), survey_id=graphene.Int()
    )
    pollTripsLegs = graphene.List(tripsLegs, tripId=graphene.Int())

    def resolve_pollActiveSurveyInfo(root, info, selectedDate):
        dev = info.context.device
        if not dev:
            raise GraphQLError("Authentication required", [info])

        return (SurveyInfo.objects
                .get(start_day__lte=selectedDate + timedelta(days=7), end_day__gte=selectedDate))

    def resolve_pollSurveyInfo(root, info):
        dev = info.context.device
        if not dev:
            raise GraphQLError("Authentication required", [info])

        return SurveyInfo.objects.all()

    def resolve_pollUserSurvey(root, info, survey_id=""):
        dev = info.context.device
        if not dev:
            raise GraphQLError("Authentication required", [info])

        if survey_id != "":
            return Partisipants.objects.filter(survey_info=survey_id, device=dev)
        else:
            return Partisipants.objects.filter(device=dev)

    def resolve_pollSurveyQuestions(root, info, question_type, survey_id=""):
        dev = info.context.device
        if not dev:
            raise GraphQLError("Authentication required", [info])

        if survey_id != "":
            return Questions.objects.filter(
                is_use=True, question_type=question_type, survey_info=survey_id
            )
        else:
            return Questions.objects.filter(is_use=True, question_type=question_type)

    def resolve_pollSurveyQuestion(root, info, question_id):
        dev = info.context.device
        if not dev:
            raise GraphQLError("Authentication required", [info])

        return Questions.objects.filter(is_use=True, pk=question_id)

    def resolve_pollDayTrips(root, info, day, survey_id=""):
        dev = info.context.device
        if not dev:
            raise GraphQLError("Authentication required", [info])

        if survey_id != "":
            partisipantObj = Partisipants.objects.get(survey_info=survey_id, device=dev)
        else:
            partisipantObj = Partisipants.objects.filter(device=dev)[:1]

        tripsObj = Trips.objects.filter(
            partisipant=partisipantObj, start_time__date=day, deleted=False
        )

        return tripsObj

    def resolve_pollTripsLegs(root, info, tripId):
        dev = info.context.device
        if not dev:
            raise GraphQLError("Authentication required", [info])

        return Legs.objects.filter(deleted=False, trip=tripId)
