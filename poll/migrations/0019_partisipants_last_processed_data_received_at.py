# Generated by Django 3.1.9 on 2023-10-04 06:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poll', '0018_auto_20231004_0904'),
    ]

    operations = [
        migrations.AddField(
            model_name='partisipants',
            name='last_processed_data_received_at',
            field=models.DateTimeField(null=True),
        ),
    ]
