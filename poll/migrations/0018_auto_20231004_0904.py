# Generated by Django 3.1.9 on 2023-10-04 06:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('poll', '0017_originaltrip'),
    ]

    operations = [
        migrations.AlterField(
            model_name='originaltrip',
            name='trip',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='original_trip_data', to='poll.trips'),
        ),
    ]