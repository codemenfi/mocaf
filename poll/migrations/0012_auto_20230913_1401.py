# Generated by Django 3.1.9 on 2023-09-13 11:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("poll", "0011_auto_20230913_1356"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="trips",
            name="purpose",
        ),
        migrations.AddConstraint(
            model_name="trips",
            constraint=models.CheckConstraint(
                check=models.Q(
                    purpose__in=[
                        "travel_to_work_trip",
                        "travel_to_work_trip",
                        "school_trip",
                        "leisure_trip",
                        "shopping_trip",
                        "affair_trip",
                        "passenger_transport_trip",
                        "",
                        "tyhja",
                    ]
                ),
                name="purpose",
            ),
        ),
    ]
