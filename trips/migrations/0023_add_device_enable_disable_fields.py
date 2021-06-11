# Generated by Django 3.1.8 on 2021-06-11 07:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0022_add_device_friendly_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='disabled_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='device',
            name='enabled_at',
            field=models.DateTimeField(null=True),
        ),
    ]