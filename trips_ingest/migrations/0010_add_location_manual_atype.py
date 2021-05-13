# Generated by Django 3.1.7 on 2021-03-29 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips_ingest', '0009_add_more_location_fields'),
    ]

    operations = [
        migrations.RunSQL("""
            ALTER TABLE "trips_ingest_location" ADD COLUMN "manual_atype" varchar(20) NULL;
        """, reverse_sql="""
            ALTER TABLE "trips_ingest_location" DROP COLUMN "manual_atype";
        """),
    ]
