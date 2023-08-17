# Generated by Django 3.1.9 on 2023-06-30 09:51

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('gtfs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Agency',
            fields=[
                ('id', models.TextField(db_column='agency_id', primary_key=True, serialize=False)),
                ('name', models.TextField(blank=True, db_column='agency_name', null=True)),
                ('agency_url', models.TextField(blank=True, null=True)),
                ('agency_timezone', models.TextField(blank=True, null=True)),
                ('agency_lang', models.TextField(blank=True, null=True)),
                ('agency_phone', models.TextField(blank=True, null=True)),
                ('agency_fare_url', models.TextField(blank=True, null=True)),
                ('agency_email', models.TextField(blank=True, null=True)),
                ('bikes_policy_url', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."agency',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Calendar',
            fields=[
                ('service_id', models.TextField(primary_key=True, serialize=False)),
                ('monday', models.IntegerField()),
                ('tuesday', models.IntegerField()),
                ('wednesday', models.IntegerField()),
                ('thursday', models.IntegerField()),
                ('friday', models.IntegerField()),
                ('saturday', models.IntegerField()),
                ('sunday', models.IntegerField()),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
            ],
            options={
                'db_table': 'gtfs"."calendar',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='CalendarDate',
            fields=[
                ('service_id', models.TextField(primary_key=True, serialize=False)),
                ('date', models.DateField()),
            ],
            options={
                'db_table': 'gtfs"."calendar_dates',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ContinuousPickup',
            fields=[
                ('continuous_pickup', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."continuous_pickup',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ExceptionType',
            fields=[
                ('exception_type', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."exception_types',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='FareAttribute',
            fields=[
                ('fare_id', models.TextField(primary_key=True, serialize=False)),
                ('price', models.FloatField()),
                ('currency_type', models.TextField()),
                ('transfers', models.IntegerField(blank=True, null=True)),
                ('transfer_duration', models.IntegerField(blank=True, null=True)),
                ('agency_id', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."fare_attributes',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='FareRule',
            fields=[
                ('fare_id', models.TextField(primary_key=True, serialize=False)),
                ('route_id', models.TextField(blank=True, null=True)),
                ('origin_id', models.TextField(blank=True, null=True)),
                ('destination_id', models.TextField(blank=True, null=True)),
                ('contains_id', models.TextField(blank=True, null=True)),
                ('service_id', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."fare_rules',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='FeedInfo',
            fields=[
                ('feed_index', models.AutoField(primary_key=True, serialize=False)),
                ('feed_publisher_name', models.TextField(blank=True, null=True)),
                ('feed_publisher_url', models.TextField(blank=True, null=True)),
                ('feed_timezone', models.TextField(blank=True, null=True)),
                ('feed_lang', models.TextField(blank=True, null=True)),
                ('feed_version', models.TextField(blank=True, null=True)),
                ('feed_start_date', models.DateField(blank=True, null=True)),
                ('feed_end_date', models.DateField(blank=True, null=True)),
                ('feed_id', models.TextField(blank=True, null=True)),
                ('feed_contact_url', models.TextField(blank=True, null=True)),
                ('feed_contact_email', models.TextField(blank=True, null=True)),
                ('feed_download_date', models.DateField(blank=True, null=True)),
                ('feed_file', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."feed_info',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Frequency',
            fields=[
                ('trip_id', models.TextField(primary_key=True, serialize=False)),
                ('start_time', models.TextField()),
                ('end_time', models.TextField()),
                ('headway_secs', models.IntegerField()),
                ('exact_times', models.IntegerField(blank=True, null=True)),
                ('start_time_seconds', models.IntegerField(blank=True, null=True)),
                ('end_time_seconds', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."frequencies',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='LocationType',
            fields=[
                ('location_type', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."location_types',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('payment_method', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."payment_methods',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='PickupDropoffType',
            fields=[
                ('type_id', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."pickup_dropoff_types',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Route',
            fields=[
                ('id', models.TextField(db_column='route_id', primary_key=True, serialize=False)),
                ('short_name', models.TextField(blank=True, db_column='route_short_name', null=True)),
                ('long_name', models.TextField(blank=True, db_column='route_long_name', null=True)),
                ('desc', models.TextField(blank=True, db_column='route_desc', null=True)),
                ('route_url', models.TextField(blank=True, null=True)),
                ('route_color', models.TextField(blank=True, null=True)),
                ('route_text_color', models.TextField(blank=True, null=True)),
                ('route_sort_order', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."routes',
                'ordering': ('feed', 'route_sort_order', 'id'),
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='RouteType',
            fields=[
                ('id', models.IntegerField(db_column='route_type', primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."route_types',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Shape',
            fields=[
                ('shape_id', models.TextField(primary_key=True, serialize=False)),
                ('shape_pt_lat', models.FloatField()),
                ('shape_pt_lon', models.FloatField()),
                ('shape_pt_sequence', models.IntegerField()),
                ('shape_dist_traveled', models.FloatField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."shapes',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Stop',
            fields=[
                ('stop_id', models.TextField(primary_key=True, serialize=False)),
                ('stop_name', models.TextField(blank=True, null=True)),
                ('stop_desc', models.TextField(blank=True, null=True)),
                ('stop_lat', models.FloatField(blank=True, null=True)),
                ('stop_lon', models.FloatField(blank=True, null=True)),
                ('zone_id', models.TextField(blank=True, null=True)),
                ('stop_url', models.TextField(blank=True, null=True)),
                ('stop_code', models.TextField(blank=True, null=True)),
                ('stop_street', models.TextField(blank=True, null=True)),
                ('stop_city', models.TextField(blank=True, null=True)),
                ('stop_region', models.TextField(blank=True, null=True)),
                ('stop_postcode', models.TextField(blank=True, null=True)),
                ('stop_country', models.TextField(blank=True, null=True)),
                ('stop_timezone', models.TextField(blank=True, null=True)),
                ('direction', models.TextField(blank=True, null=True)),
                ('position', models.TextField(blank=True, null=True)),
                ('parent_station', models.TextField(blank=True, null=True)),
                ('vehicle_type', models.IntegerField(blank=True, null=True)),
                ('platform_code', models.TextField(blank=True, null=True)),
                ('the_geom', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=3067)),
            ],
            options={
                'db_table': 'gtfs"."stops',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='StopTime',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('arrival_time', models.DurationField(blank=True, null=True)),
                ('departure_time', models.DurationField(blank=True, null=True)),
                ('stop_sequence', models.IntegerField()),
                ('stop_headsign', models.TextField(blank=True, null=True)),
                ('shape_dist_traveled', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('continuous_drop_off', models.IntegerField(blank=True, null=True)),
                ('arrival_time_seconds', models.IntegerField(blank=True, null=True)),
                ('departure_time_seconds', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."stop_times',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Timepoint',
            fields=[
                ('timepoint', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."timepoints',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Transfer',
            fields=[
                ('feed_index', models.IntegerField(primary_key=True, serialize=False)),
                ('from_stop_id', models.TextField(blank=True, null=True)),
                ('to_stop_id', models.TextField(blank=True, null=True)),
                ('min_transfer_time', models.IntegerField(blank=True, null=True)),
                ('from_route_id', models.TextField(blank=True, null=True)),
                ('to_route_id', models.TextField(blank=True, null=True)),
                ('service_id', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."transfers',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='TransferType',
            fields=[
                ('transfer_type', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."transfer_types',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Trip',
            fields=[
                ('service_id', models.TextField()),
                ('trip_id', models.TextField(primary_key=True, serialize=False)),
                ('trip_headsign', models.TextField(blank=True, null=True)),
                ('direction_id', models.IntegerField(blank=True, null=True)),
                ('block_id', models.TextField(blank=True, null=True)),
                ('shape_id', models.TextField(blank=True, null=True)),
                ('trip_short_name', models.TextField(blank=True, null=True)),
                ('direction', models.TextField(blank=True, null=True)),
                ('schd_trip_id', models.TextField(blank=True, null=True)),
                ('trip_type', models.TextField(blank=True, null=True)),
                ('exceptional', models.IntegerField(blank=True, null=True)),
                ('bikes_allowed', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."trips',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='WheelchairAccessible',
            fields=[
                ('wheelchair_accessible', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."wheelchair_accessible',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='WheelchairBoarding',
            fields=[
                ('wheelchair_boarding', models.IntegerField(primary_key=True, serialize=False)),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gtfs"."wheelchair_boardings',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ShapeGeometry',
            fields=[
                ('shape', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='gtfs.shape')),
                ('length', models.DecimalField(decimal_places=2, max_digits=12)),
                ('the_geom', django.contrib.gis.db.models.fields.LineStringField(blank=True, null=True, srid=3067)),
            ],
            options={
                'db_table': 'gtfs"."shape_geoms',
                'managed': False,
            },
        ),
    ]