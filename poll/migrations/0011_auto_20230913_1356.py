# Generated by Django 3.1.9 on 2023-09-13 10:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poll', '0010_partisipants_registered_to_survey_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trips',
            name='purpose',
            field=models.CharField(choices=[('travel_to_work_trip', 'Työmatka'), ('travel_to_work_trip', 'Työasiamatka'), ('school_trip', 'Koulu- tai opiskelumatka'), ('leisure_trip', 'Vapaa-ajanmatka'), ('shopping_trip', 'Ostosmatka'), ('affair_trip', 'Asiointimatka'), ('passenger_transport_trip', 'Kyyditseminen'), ('', 'Tyhjä')], default='', max_length=24),
        ),
    ]
