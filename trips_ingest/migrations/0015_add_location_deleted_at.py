# Generated by Django 3.1.7 on 2021-03-29 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips_ingest', '0014_receivedata_device'),
    ]

    operations = [
        migrations.RunSQL("""
            ALTER TABLE "trips_ingest_location" ADD COLUMN "deleted_at" timestamp with time zone NULL;
        """, reverse_sql="""
            ALTER TABLE "trips_ingest_location" DROP COLUMN "deleted_at";
        """),
    ]
