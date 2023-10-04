from django.db.models import F
from poll.models import Trips
import xlsxwriter


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


def format_question_answers(answers_json):
    if type(answers_json) is str:
        return ""

    result = ""
    for key, value in answers_json.items():
        result += f"{key}: {value}\n"

    return result


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
    worksheet.write(row, col + 12, "Taustakysymykset 1")
    worksheet.write(row, col + 13, "Taustakysymykset 2")

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
        worksheet.write(
            row,
            col + 12,
            format_question_answers(trip.partisipant.back_question_answers),
            wrap,
        )
        worksheet.write(
            row,
            col + 13,
            format_question_answers(trip.partisipant.feeling_question_answers),
            wrap,
        )
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

    # start_time = models.DateTimeField()
    # end_time = models.DateTimeField()
    #
    # trip_length = models.FloatField(null=True)
    #
    # carbon_footprint = models.FloatField(null=True)
    #
    # nr_passengers = models.IntegerField(null=True)
    #
    # transport_mode = models.CharField(max_length=20, null=True)
