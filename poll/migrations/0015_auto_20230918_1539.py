# Generated by Django 3.1.9 on 2023-09-18 12:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('poll', '0013_auto_20230918_1529'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='trips',
            name='startmunicipality',
        ),
        migrations.RemoveConstraint(
            model_name='trips',
            name='endmunicipality',
        ),
    ]
