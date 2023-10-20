from django.db.models import QuerySet
from feedback.models import DeviceFeedback
import xlsxwriter

import pytz
from django.conf import settings

LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)


def export_feedbacks(feedbacks: QuerySet[DeviceFeedback]):
    workbook = xlsxwriter.Workbook("feedbacks.xlsx")

    worksheet = workbook.add_worksheet()

    worksheet.write(0, 0, "id")
    worksheet.write(0, 1, "device")
    worksheet.write(0, 2, "trip")
    worksheet.write(0, 3, "trip length")
    worksheet.write(0, 4, "leg")
    worksheet.write(0, 5, "leg length")
    worksheet.write(0, 6, "transport mode")
    worksheet.write(0, 7, "user corrected transport mode")
    worksheet.write(0, 8, "transport mode variant")
    worksheet.write(0, 9, "user corrected transport mode variant")
    worksheet.write(0, 10, "mode confidence")
    worksheet.write(0, 11, "estimated mode")
    worksheet.write(0, 12, "duration")
    worksheet.write(0, 13, "start time")
    worksheet.write(0, 13, "end time")
    worksheet.write(0, 14, "comment")

    row = 1

    for feedback in feedbacks:
        worksheet.write(row, 0, feedback.id)
        worksheet.write(row, 1, feedback.device.id)
        worksheet.write(row, 2, feedback.trip.id)
        worksheet.write(row, 3, feedback.trip.length)
        worksheet.write(row, 4, feedback.leg.id)
        worksheet.write(row, 5, feedback.leg.length)
        worksheet.write(row, 6, feedback.leg.mode)
        worksheet.write(row, 7, feedback.leg.user_corrected_mode)
        worksheet.write(row, 8, feedback.leg.mode_variant)
        worksheet.write(row, 9, feedback.leg.user_corrected_mode_variant)
        worksheet.write(row, 10, feedback.leg.mode_confidence)
        worksheet.write(row, 11, feedback.leg.estimated_mode)

        duration = (
            feedback.leg.end_time - feedback.leg.start_time
        ).total_seconds() / 60
        worksheet.write(row, 12, duration)
        start_time = feedback.leg.start_time.astimezone(LOCAL_TZ)
        worksheet.write(row, 13, start_time)
        end_time = feedback.leg.start_time.astimezone(LOCAL_TZ)
        worksheet.write(row, 14, end_time)
        worksheet.write(row, 15, feedback.comment)
        row += 1

    workbook.close()
