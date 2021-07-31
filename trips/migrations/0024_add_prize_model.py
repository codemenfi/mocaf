# Generated by Django 3.1.9 on 2021-06-23 19:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0023_add_device_enable_disable_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leg',
            name='carbon_footprint',
            field=models.FloatField(help_text='Carbon footprint in g CO2e'),
        ),
        migrations.AlterField(
            model_name='leg',
            name='length',
            field=models.FloatField(help_text='Length in m'),
        ),
    ]