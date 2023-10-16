from django.db.models import F
from poll.models import Trips, Partisipants, OriginalTrip
import xlsxwriter
import json

import codecs

from trips.tests.conftest import partisipants


def partisipant_trips(partisipant):
    return Trips.objects.filter(
        partisipant=partisipant,
        start_time__date__gte=partisipant.survey.start_day,
        start_time__date__lte=partisipant.survey.end_day,
        deleted=False,
    )


def survey_trips(survey):
    return Trips.objects.filter(
        partisipant__survey_info=survey,
        start_time__date__gte=F("partisipant__start_date"),
        start_time__date__lte=F("partisipant__end_date"),
        deleted=False,
    ).order_by("partisipant__pk", "start_time")


transport_mode_texts = {
    "walk": "Kävely",
    "bicycle": "Polkupyörä",
    "escooter": "Sähköpotkulauta",
    "bus": "Bussi",
    "tram": "Raitiovaunu",
    "train": "Juna",
    "car_driver": "Henkilöauto (kuljettaja)",
    "car_passenger": "Henkilöauto (matkustaja)",
    "taxi": "Taksi",
    "other": "Muu",
}

purpose_texts = {
    "travel_to_work_trip": "Työmatka",
    "business_trip": "Työasiamatka",
    "school_trip": "Koulu- tai opiskelumatka",
    "shopping_trip": "Ostosmatka",
    "leisure_trip": "Vapaa-ajanmatka",
    "affair_trip": "Asiointimatka",
    "passenger_transport_trip": "Kyyditseminen",
    "tyhja": "",
}

question_columns = {
    "Sukupuoli": 1,
    "Syntymävuosi": 2,
    "Asuinpaikan postinumero": 3,
    "Korkein suorittamasi koulutus?": 4,
    "Asumismuoto": 5,
    "Henkilöauton ajokortti (B-kortti)": 6,
    "Onko kotitaloudellasi auto aina käytettävissä?": 7,
    "Kun liikut autolla, oletko useammin": 8,
    "Kävelyn, pyöräilyn ja joukkoliikenteen olosuhteita tulee kehittää, vaikka se tarkoittaisi paikoin autoliikenteen olosuhteiden heikentymistä.": 9,
    "Kävelyn, pyöräilyn ja joukkoliikenteen olosuhteita tulee kehittää, mutta autoliikenteen olosuhteiden tulee säilyä vähintään nykyisellään.": 10,
}


def parse_question_answers(answers_json):
    if type(answers_json) is str:
        answers_json = json.loads(answers_json)

    return None


def export_survey_trips_json(survey):
    partisipants = Partisipants.objects.filter(survey_info=survey)

    data = list()
    for partisipant in partisipants:
        partisipant_data = dict()
        partisipant_data["partisipant"] = partisipant.pk

        trips = Trips.objects.filter(
            start_time__date__gte=F("partisipant__start_date"),
            start_time__date__lte=F("partisipant__end_date"),
            deleted=False,
            approved=True,
        )

        unapproved = Trips.objects.filter(
            start_time__date__gte=F("partisipant__start_date"),
            start_time__date__lte=F("partisipant__end_date"),
            deleted=False,
            approved=False,
        ).count()

        trips_data = list()
        for trip in trips:
            trip_data = trip.to_json()
            legs_data = list()
            for leg in trip.legs_set.filter(deleted=False):
                legs_data.append(leg.to_json())
            trip_data["legs"] = legs_data

            trip_data["original_trip_data"] = None
            original_trip_data = OriginalTrip.objects.filter(trip=trip).first()
            if original_trip_data:
                trip_data["original_trip_data"] = json.loads(original_trip_data)

            trips_data.append(trip_data)

        partisipant_data["trips"] = trips_data
        partisipant_data["unapproved_trips_count"] = unapproved
        if partisipant.back_question_answers:
            partisipant_data["back_questions_1"] = parse_question_answers(
                partisipant.back_question_answers
            )
        if partisipant.feeling_question_answers:
            partisipant_data["back_questions_2"] = parse_question_answers(
                partisipant.feeling_question_answers
            )

        partisipant_data["approved"] = partisipant.approved

        data.append(partisipant_data)

    with open("survey_trips.json", "w", encoding="UTF-8") as outfile:
        json.dump(data, outfile, indent=4, ensure_ascii=False)


def export_survey_trips(survey):
    trips = survey_trips(survey)

    workbook = xlsxwriter.Workbook("survey_trips.xlsx")
    worksheet = workbook.add_worksheet()

    wrap = workbook.add_format({"text_wrap": True})

    row = 0
    col = 0

    worksheet.write(row, col, "Vastaajan tunniste")
    worksheet.write(row, col + 1, "Matkan tunniste")
    worksheet.write(row, col + 2, "Tarkastettu")
    worksheet.write(row, col + 3, "Matkan tarkoitus")
    worksheet.write(row, col + 4, "Lähtöaika")
    worksheet.write(row, col + 5, "Saapumisaika")
    worksheet.write(row, col + 6, "Lähtöpaikka")
    worksheet.write(row, col + 7, "Määränpää")
    worksheet.write(row, col + 8, "Matkan pituus")
    worksheet.write(row, col + 9, "Matkanosan tunniste")
    worksheet.write(row, col + 10, "Matkanosan pituus")
    worksheet.write(row, col + 11, "Matkanosan kulkutapa")

    for key, value in question_columns.items():
        worksheet.write(row, value + 11, key)

    row += 1

    for trip in trips:
        worksheet.write(row, col, trip.partisipant.pk)
        worksheet.write(row, col + 1, trip.pk)
        worksheet.write(row, col + 2, "Kyllä" if trip.approved else "Ei")
        worksheet.write(row, col + 3, purpose_texts.get(trip.purpose, ""))
        worksheet.write(row, col + 4, trip.start_time.strftime("%d.%m.%Y %H:%M"))
        worksheet.write(row, col + 5, trip.end_time.strftime("%d.%m.%Y %H:%M"))
        worksheet.write(row, col + 6, trip.start_municipality)
        worksheet.write(row, col + 7, trip.end_municipality)
        worksheet.write(row, col + 8, trip.length)

        back_questions = parse_question_answers(trip.partisipant.back_question_answers)
        if back_questions:
            for question in back_questions:
                key = question["questionId"]
                value = question["answer"]
                worksheet.write(row, question_columns[key] + 11, value)

        feeling_questions = parse_question_answers(
            trip.partisipant.feeling_question_answers
        )
        if feeling_questions:
            for question in feeling_questions:
                key = question["questionId"]
                value = question["answer"]
                worksheet.write(row, question_columns[key] + 11, value)

        row += 1

        for leg in trip.legs_set.all():
            worksheet.write(row, col + 9, leg.id)
            worksheet.write(row, col + 10, leg.trip_length)
            worksheet.write(
                row, col + 11, transport_mode_texts.get(leg.transport_mode, "")
            )
            row += 1

    workbook.close()

    return workbook
