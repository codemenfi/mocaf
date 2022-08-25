# Generated by Django 3.1.9 on 2022-08-25 09:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0011_add_api_activity_model'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='devicedailyapiactivity',
            options={'ordering': ('device', '-date')},
        ),
        migrations.AddField(
            model_name='devicedailyapiactivity',
            name='last_user_agent',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]