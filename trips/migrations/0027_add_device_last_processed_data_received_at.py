# Generated by Django 3.1.9 on 2022-08-08 13:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0026_device_account_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='last_processed_data_received_at',
            field=models.DateTimeField(null=True),
        ),
    ]
