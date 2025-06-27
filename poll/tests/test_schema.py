import pytest
from datetime import date, timedelta
from django.utils import timezone
from freezegun import freeze_time

from poll.tests.factories import (
    SurveyInfoFactory,
    ParticipantsFactory,
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
