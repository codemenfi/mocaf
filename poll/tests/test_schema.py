import pytest
from datetime import date, timedelta, datetime
from django.utils import timezone
from freezegun import freeze_time

from poll.tests.factories import (
    SurveyInfoFactory,
    ParticipantsFactory,
    DayInfoFactory,
    TripsFactory,
    LegsFactory,
)
from poll.models import Partisipants, DayInfo

pytestmark = pytest.mark.django_db


@freeze_time("2023-07-15")
def test_enroll_to_survey_success(graphql_client_query_data, uuid, token):
    """Test successful enrollment to an active survey"""
    # Create an active survey
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=3
    )

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )

    assert data["pollEnrollToSurvey"]["ok"] is True

    # Verify participant was created
    participant = Partisipants.objects.get(survey_info=survey)
    assert str(participant.device.uuid) == uuid
    assert participant.approved is False
    assert participant.start_date == date(2023, 7, 16)  # Next day
    assert participant.end_date == date(2023, 7, 18)  # Start date + days - 1
    assert participant.registered_to_survey_at is not None

    # Verify device survey_enabled was set to True
    participant.device.refresh_from_db()
    assert participant.device.survey_enabled is True

    # Verify DayInfo objects were created for each survey day
    day_infos = DayInfo.objects.filter(partisipant=participant)
    assert day_infos.count() == 3
    expected_dates = [date(2023, 7, 16), date(2023, 7, 17), date(2023, 7, 18)]
    actual_dates = [day_info.date for day_info in day_infos.order_by("date")]
    assert actual_dates == expected_dates


@freeze_time("2023-07-15")
def test_enroll_to_survey_with_question_answers(graphql_client_query_data, uuid, token):
    """Test enrollment with background and feeling question answers"""
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=3
    )

    back_answers = '{"age": 25, "occupation": "student"}'
    feeling_answers = '{"mood": "good", "energy": "high"}'

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!, $backAnswers: String!, $feelingAnswers: String!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(
                surveyId: $surveyId, 
                backQuestionAnswers: $backAnswers, 
                feelingQuestionAnswers: $feelingAnswers
            ) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "surveyId": survey.id,
            "backAnswers": back_answers,
            "feelingAnswers": feeling_answers,
        },
    )

    assert data["pollEnrollToSurvey"]["ok"] is True

    # Verify participant was created with question answers
    participant = Partisipants.objects.get(survey_info=survey)
    assert participant.back_question_answers == back_answers
    assert participant.feeling_question_answers == feeling_answers


def test_enroll_to_survey_already_enrolled(
    graphql_client_query, contains_error, uuid, token, device
):
    """Test that enrollment fails if user is already enrolled"""
    survey = SurveyInfoFactory()

    # Use the existing device fixture
    ParticipantsFactory(device=device, survey_info=survey)

    response = graphql_client_query(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )

    assert contains_error(response, message="User has allready enrolled to survey")


def test_enroll_to_survey_survey_not_found(
    graphql_client_query, contains_error, uuid, token
):
    """Test that enrollment fails if survey doesn't exist"""
    non_existent_survey_id = 99999

    response = graphql_client_query(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": non_existent_survey_id},
    )

    # This should fail because the survey doesn't exist
    assert "errors" in response


@freeze_time("2023-07-15")
def test_enroll_to_survey_sets_correct_dates(graphql_client_query_data, uuid, token):
    """Test that enrollment sets the correct start and end dates"""
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 20), days=3
    )

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )

    assert data["pollEnrollToSurvey"]["ok"] is True

    participant = Partisipants.objects.get(survey_info=survey)
    # Survey starts the next day (2023, 7, 16)
    assert participant.start_date == date(2023, 7, 16)
    # End date should be start_date + days - 1 = 2023-07-16 + 3 - 1 = 2023-07-18
    assert participant.end_date == date(2023, 7, 18)


@freeze_time("2023-07-15")
def test_enroll_to_survey_creates_day_info_objects(
    graphql_client_query_data, uuid, token
):
    """Test that enrollment creates the correct number of DayInfo objects"""
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=3
    )

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )

    assert data["pollEnrollToSurvey"]["ok"] is True

    participant = Partisipants.objects.get(survey_info=survey)
    day_infos = DayInfo.objects.filter(partisipant=participant)

    # Should create exactly 3 DayInfo objects
    assert day_infos.count() == 3

    # All DayInfo objects should be unapproved initially
    for day_info in day_infos:
        assert day_info.approved is False


@freeze_time("2023-07-15")
def test_enroll_to_survey_enables_device_survey(graphql_client_query_data, uuid, token):
    """Test that enrollment enables survey for the device"""
    survey = SurveyInfoFactory()

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )

    assert data["pollEnrollToSurvey"]["ok"] is True

    # Verify device survey_enabled was set to True
    from trips.models import Device

    device = Device.objects.get(uuid=uuid)
    assert device.survey_enabled is True


@freeze_time("2023-07-15")
def test_mark_user_day_ready_success(graphql_client_query_data, uuid, token, device):
    """Test successful marking of a day as ready with valid trips"""
    # Create survey and participant
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=3
    )
    participant = ParticipantsFactory(device=device, survey_info=survey)

    # Create day info for the selected date
    day_info = DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=False
    )

    # Create trips with purpose and legs for the selected date
    trip1 = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 8, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 9, 0, 0)),
        purpose="travel_to_work_trip",
        approved=False,
    )
    leg1 = LegsFactory(trip=trip1)

    trip2 = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 17, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 18, 0, 0)),
        purpose="leisure_trip",
        approved=False,
    )
    leg2 = LegsFactory(trip=trip2)

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $selectedDate: Date!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollMarkUserDayReady(selectedDate: $selectedDate, surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "selectedDate": "2023-07-16",
            "surveyId": survey.id,
        },
    )

    assert data["pollMarkUserDayReady"]["ok"] is True

    # Verify trips were approved
    trip1.refresh_from_db()
    trip2.refresh_from_db()
    assert trip1.approved is True
    assert trip2.approved is True

    # Verify day info was approved
    day_info.refresh_from_db()
    assert day_info.approved is True


@freeze_time("2023-07-15")
def test_mark_user_day_ready_trip_without_legs(
    graphql_client_query, contains_error, uuid, token, device
):
    """Test that marking day ready fails if an unapproved trip has no legs"""
    survey = SurveyInfoFactory()
    participant = ParticipantsFactory(device=device, survey_info=survey)

    day_info = DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=False
    )

    # Create trip without legs
    trip = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 8, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 9, 0, 0)),
        purpose="travel_to_work_trip",
        approved=False,
    )
    # No legs created

    response = graphql_client_query(
        """
        mutation($uuid: String!, $token: String!, $selectedDate: Date!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollMarkUserDayReady(selectedDate: $selectedDate, surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "selectedDate": "2023-07-16",
            "surveyId": survey.id,
        },
    )

    assert contains_error(response, message="Trip has no legs")

    # Verify nothing was approved
    trip.refresh_from_db()
    day_info.refresh_from_db()
    assert trip.approved is False
    assert day_info.approved is False


@freeze_time("2023-07-15")
def test_mark_user_day_ready_already_approved_trips(
    graphql_client_query_data, uuid, token, device
):
    """Test marking day ready with already approved trips"""
    survey = SurveyInfoFactory()
    participant = ParticipantsFactory(device=device, survey_info=survey)

    day_info = DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=False
    )

    # Create already approved trip
    trip = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 8, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 9, 0, 0)),
        purpose="travel_to_work_trip",
        approved=True,  # Already approved
    )
    leg = LegsFactory(trip=trip)

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $selectedDate: Date!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollMarkUserDayReady(selectedDate: $selectedDate, surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "selectedDate": "2023-07-16",
            "surveyId": survey.id,
        },
    )

    assert data["pollMarkUserDayReady"]["ok"] is True

    # Verify day info was approved
    day_info.refresh_from_db()
    assert day_info.approved is True

    # Trip should remain approved
    trip.refresh_from_db()
    assert trip.approved is True


@freeze_time("2023-07-15")
def test_mark_user_day_ready_mixed_trips(
    graphql_client_query_data, uuid, token, device
):
    """Test marking day ready with mix of approved and unapproved trips"""
    survey = SurveyInfoFactory()
    participant = ParticipantsFactory(device=device, survey_info=survey)

    day_info = DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=False
    )

    # Create approved trip
    approved_trip = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 8, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 9, 0, 0)),
        purpose="travel_to_work_trip",
        approved=True,
    )
    approved_leg = LegsFactory(trip=approved_trip)

    # Create unapproved trip
    unapproved_trip = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 17, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 18, 0, 0)),
        purpose="leisure_trip",
        approved=False,
    )
    unapproved_leg = LegsFactory(trip=unapproved_trip)

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $selectedDate: Date!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollMarkUserDayReady(selectedDate: $selectedDate, surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "selectedDate": "2023-07-16",
            "surveyId": survey.id,
        },
    )

    assert data["pollMarkUserDayReady"]["ok"] is True

    # Verify both trips are approved
    approved_trip.refresh_from_db()
    unapproved_trip.refresh_from_db()
    assert approved_trip.approved is True
    assert unapproved_trip.approved is True

    # Verify day info was approved
    day_info.refresh_from_db()
    assert day_info.approved is True


@freeze_time("2023-07-15")
def test_mark_user_day_ready_no_trips(graphql_client_query_data, uuid, token, device):
    """Test marking day ready when there are no trips for the date"""
    survey = SurveyInfoFactory()
    participant = ParticipantsFactory(device=device, survey_info=survey)

    day_info = DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=False
    )

    # No trips created for this date

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $selectedDate: Date!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollMarkUserDayReady(selectedDate: $selectedDate, surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "selectedDate": "2023-07-16",
            "surveyId": survey.id,
        },
    )

    assert data["pollMarkUserDayReady"]["ok"] is True

    # Verify day info was approved even with no trips
    day_info.refresh_from_db()
    assert day_info.approved is True


@freeze_time("2023-07-15")
def test_mark_user_day_ready_deleted_trips_ignored(
    graphql_client_query_data, uuid, token, device
):
    """Test that deleted trips are ignored when marking day ready"""
    survey = SurveyInfoFactory()
    participant = ParticipantsFactory(device=device, survey_info=survey)

    day_info = DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=False
    )

    # Create deleted trip (should be ignored)
    deleted_trip = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 8, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 9, 0, 0)),
        purpose="travel_to_work_trip",
        approved=False,
        deleted=True,  # Deleted trip
    )
    deleted_leg = LegsFactory(trip=deleted_trip)

    # Create valid trip
    valid_trip = TripsFactory(
        partisipant=participant,
        start_time=timezone.make_aware(datetime(2023, 7, 16, 17, 0, 0)),
        end_time=timezone.make_aware(datetime(2023, 7, 16, 18, 0, 0)),
        purpose="leisure_trip",
        approved=False,
        deleted=False,
    )
    valid_leg = LegsFactory(trip=valid_trip)

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $selectedDate: Date!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollMarkUserDayReady(selectedDate: $selectedDate, surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "selectedDate": "2023-07-16",
            "surveyId": survey.id,
        },
    )

    assert data["pollMarkUserDayReady"]["ok"] is True

    # Verify only valid trip was approved
    deleted_trip.refresh_from_db()
    valid_trip.refresh_from_db()
    assert deleted_trip.approved is False  # Should remain unapproved
    assert valid_trip.approved is True

    # Verify day info was approved
    day_info.refresh_from_db()
    assert day_info.approved is True


@freeze_time("2023-07-15")
def test_mark_user_day_ready_wrong_date(
    graphql_client_query, contains_error, uuid, token, device
):
    """Test that marking day ready fails for date with no day info"""
    survey = SurveyInfoFactory()
    participant = ParticipantsFactory(device=device, survey_info=survey)

    # Create day info for different date
    day_info = DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 17), approved=False
    )

    # Try to mark a date that has no day info
    response = graphql_client_query(
        """
        mutation($uuid: String!, $token: String!, $selectedDate: Date!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollMarkUserDayReady(selectedDate: $selectedDate, surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={
            "uuid": uuid,
            "token": token,
            "selectedDate": "2023-07-16",  # Date with no day info
            "surveyId": survey.id,
        },
    )

    # This should fail because there's no DayInfo for the selected date
    assert "errors" in response


@freeze_time("2023-07-15")
def test_mark_user_day_ready_enables_device_survey(
    graphql_client_query_data, uuid, token
):
    """Test that enrollment enables survey for the device"""
    survey = SurveyInfoFactory()

    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollEnrollToSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )

    assert data["pollEnrollToSurvey"]["ok"] is True

    # Verify device survey_enabled was set to True
    from trips.models import Device

    device = Device.objects.get(uuid=uuid)
    assert device.survey_enabled is True


@freeze_time("2023-07-15")
def test_approve_user_survey_success(graphql_client_query_data, uuid, token, device):
    """Test successful approval of user survey when all days are approved"""
    # Create survey and participant
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=3
    )
    participant = ParticipantsFactory(device=device, survey_info=survey, approved=False)
    
    # Create day info objects for all survey days - all approved
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=True
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 17), approved=True
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 18), approved=True
    )
    
    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollApproveUserSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )
    
    assert data["pollApproveUserSurvey"]["ok"] is True
    
    # Verify participant was approved
    participant.refresh_from_db()
    assert participant.approved is True


@freeze_time("2023-07-15")
def test_approve_user_survey_with_unapproved_days(
    graphql_client_query, contains_error, uuid, token, device
):
    """Test that approval fails when there are unapproved days"""
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=3
    )
    participant = ParticipantsFactory(device=device, survey_info=survey, approved=False)
    
    # Create day info objects - some unapproved
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=True
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 17), approved=False  # Unapproved
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 18), approved=True
    )
    
    response = graphql_client_query(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollApproveUserSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )
    
    assert contains_error(response, message="There are non approved days")
    
    # Verify participant was not approved
    participant.refresh_from_db()
    assert participant.approved is False


@freeze_time("2023-07-15")
def test_approve_user_survey_participant_not_found(
    graphql_client_query, contains_error, uuid, token
):
    """Test that approval fails when participant doesn't exist for the survey"""
    survey = SurveyInfoFactory()
    
    # No participant created for this survey and device
    
    response = graphql_client_query(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollApproveUserSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )
    
    # Should fail because participant doesn't exist
    assert "errors" in response


@freeze_time("2023-07-15")
def test_approve_user_survey_already_approved(
    graphql_client_query_data, uuid, token, device
):
    """Test approval when participant is already approved"""
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=3
    )
    participant = ParticipantsFactory(
        device=device, survey_info=survey, approved=True  # Already approved
    )
    
    # Create all day info objects as approved
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=True
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 17), approved=True
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 18), approved=True
    )
    
    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollApproveUserSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )
    
    assert data["pollApproveUserSurvey"]["ok"] is True
    
    # Verify participant remains approved
    participant.refresh_from_db()
    assert participant.approved is True


@freeze_time("2023-07-15")
def test_approve_user_survey_no_days(graphql_client_query_data, uuid, token, device):
    """Test approval when participant has no day info objects"""
    survey = SurveyInfoFactory()
    participant = ParticipantsFactory(device=device, survey_info=survey, approved=False)
    
    # No DayInfo objects created
    
    data = graphql_client_query_data(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollApproveUserSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )
    
    assert data["pollApproveUserSurvey"]["ok"] is True
    
    # Verify participant was approved
    participant.refresh_from_db()
    assert participant.approved is True


@freeze_time("2023-07-15")
def test_approve_user_survey_multiple_unapproved_days(
    graphql_client_query, contains_error, uuid, token, device
):
    """Test that approval fails when there are multiple unapproved days"""
    survey = SurveyInfoFactory(
        start_day=date(2023, 7, 15), end_day=date(2023, 7, 18), days=4
    )
    participant = ParticipantsFactory(device=device, survey_info=survey, approved=False)
    
    # Create day info objects - multiple unapproved
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 16), approved=False  # Unapproved
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 17), approved=True
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 18), approved=False  # Unapproved
    )
    DayInfoFactory(
        partisipant=participant, date=date(2023, 7, 19), approved=False  # Unapproved
    )
    
    response = graphql_client_query(
        """
        mutation($uuid: String!, $token: String!, $surveyId: ID!)
        @device(uuid: $uuid, token: $token) {
            pollApproveUserSurvey(surveyId: $surveyId) {
                ok
            }
        }
        """,
        variables={"uuid": uuid, "token": token, "surveyId": survey.id},
    )
    
    assert contains_error(response, message="There are non approved days")
    
    # Verify participant was not approved
    participant.refresh_from_db()
    assert participant.approved is False
