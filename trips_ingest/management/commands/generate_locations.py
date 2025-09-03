import csv
import uuid
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.contrib.gis.gdal import SpatialReference, CoordTransform
from django.conf import settings
from trips_ingest.models import Location

# You can use https://nmeagen.org/ to create routes

class Command(BaseCommand):
    help = "Generate Location records from GPS coordinates in CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to CSV file containing GPS coordinates (lat,lon format)",
        )
        parser.add_argument(
            "--uuid",
            type=str,
            help="UUID for the device (default: generates random UUID)",
        )
        parser.add_argument(
            "--start-time",
            type=str,
            default=datetime.now().isoformat(),
            help="Start time for the first location (ISO format, default: now)",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Time interval between locations in seconds (default: 60)",
        )
        parser.add_argument(
            "--activity-type",
            type=str,
            choices=[
                "unknown",
                "still",
                "on_foot",
                "walking",
                "running",
                "on_bicycle",
                "in_vehicle",
            ],
            default="unknown",
            help="Activity type for all locations (default: unknown)",
        )
        parser.add_argument(
            "--activity-confidence",
            type=float,
            default=80.0,
            help="Activity confidence value (0-100, default: 80.0)",
        )
        parser.add_argument(
            "--location-error",
            type=float,
            default=5.0,
            help="Location error value (0-100, default: 5.0)",
        )
        parser.add_argument(
            "--speed",
            type=float,
            default=0.0,
            help="Speed in m/s (default: 0.0)",
        )
        parser.add_argument(
            "--speed-error",
            type=float,
            default=5.0,
            help="Speed error value (0-100, default: 5.0)",
        )
        parser.add_argument(
            "--delimiter",
            type=str,
            default=",",
            help="CSV delimiter (default: ,)",
        )
        parser.add_argument(
            "--read-activity-from-csv",
            action="store_true",
            help="Read activity type from the last column of CSV (overrides --activity-type)",
        )
        parser.add_argument(
            "--randomize-activities",
            action="store_true", 
            help="Generate random activity types with realistic clustering (overrides --activity-type)",
        )
        parser.add_argument(
            "--min-segment-length",
            type=int,
            default=5,
            help="Minimum number of consecutive points per activity type when randomizing (default: 5)",
        )
        parser.add_argument(
            "--max-segment-length",
            type=int,
            default=20,
            help="Maximum number of consecutive points per activity type when randomizing (default: 20)",
        )

    def generate_random_activities(self, total_points, min_segment=5, max_segment=20):
        """
        Generate a sequence of activity types with realistic clustering.
        Ensures multiple consecutive points have the same activity type.
        """
        # Available activity types for random generation
        activity_types = [
            "on_foot", "walking", "on_bicycle", "in_vehicle", 
            "still"  # Include still periods for realistic trips
        ]
        
        activities = []
        remaining_points = total_points
        
        while remaining_points > 0:
            # Choose random activity type
            activity = random.choice(activity_types)
            
            # Choose segment length (at least min_segment, at most remaining points)
            segment_length = min(
                random.randint(min_segment, max_segment), 
                remaining_points
            )
            
            # Add this activity type for the segment
            activities.extend([activity] * segment_length)
            remaining_points -= segment_length
        
        return activities

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        device_uuid = options["uuid"] or str(uuid.uuid4())
        start_time = datetime.fromisoformat(options["start_time"])
        interval = timedelta(seconds=options["interval"])
        activity_type = options["activity_type"]
        activity_confidence = options["activity_confidence"]
        location_error = options["location_error"]
        speed = options["speed"]
        speed_error = options["speed_error"]
        delimiter = options["delimiter"]
        read_activity_from_csv = options["read_activity_from_csv"]
        randomize_activities = options["randomize_activities"]
        min_segment_length = options["min_segment_length"]
        max_segment_length = options["max_segment_length"]

        # Validate confidence and error values
        if not 0.0 <= activity_confidence <= 100.0:
            self.stdout.write(
                self.style.ERROR("Error: Activity confidence must be between 0 and 100")
            )
            return

        if not 0.0 <= location_error <= 100.0:
            self.stdout.write(
                self.style.ERROR("Error: Location error must be between 0 and 100")
            )
            return

        if speed < 0.0:
            self.stdout.write(self.style.ERROR("Error: Speed must be non-negative"))
            return

        if not 0.0 <= speed_error <= 100.0:
            self.stdout.write(
                self.style.ERROR("Error: Speed error must be between 0 and 100")
            )
            return

        # Set up coordinate transformation
        gps_srs = SpatialReference(4326)  # WGS84
        local_srs = SpatialReference(settings.LOCAL_SRS)  # ETRS-TM35-FIN
        gps_to_local = CoordTransform(gps_srs, local_srs)

        self.stdout.write(f"Reading GPS coordinates from: {csv_file}")
        self.stdout.write(f"Device UUID: {device_uuid}")
        self.stdout.write(f"Start time: {start_time}")
        self.stdout.write(f"Interval: {interval}")
        self.stdout.write(f"Activity type: {activity_type}")
        self.stdout.write(f"Activity confidence: {activity_confidence}")
        self.stdout.write(f"Location error: {location_error}")
        self.stdout.write(f"Speed: {speed} m/s")
        self.stdout.write(f"Speed error: {speed_error}")

        coordinates = []
        csv_activities = []  # Store activity types read from CSV

        try:
            with open(csv_file, "r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file, delimiter=delimiter)

                for row_num, row in enumerate(reader, start=1):
                    if len(row) < 2:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Warning: Skipping row {row_num} - insufficient data: {row}"
                            )
                        )
                        continue

                    try:
                        lat = float(row[0].strip())
                        lon = float(row[1].strip())
                        coordinates.append((lat, lon))
                        
                        # Read activity type from last column if requested
                        if read_activity_from_csv and len(row) >= 3:
                            activity_from_csv = row[-1].strip()
                            # Validate activity type
                            valid_activities = [
                                "unknown", "still", "on_foot", "walking", 
                                "running", "on_bicycle", "in_vehicle"
                            ]
                            if activity_from_csv in valid_activities:
                                csv_activities.append(activity_from_csv)
                            else:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"Warning: Invalid activity type '{activity_from_csv}' in row {row_num}, using 'unknown'"
                                    )
                                )
                                csv_activities.append("unknown")
                        else:
                            csv_activities.append(None)  # Will use default or randomized

                    except ValueError as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Warning: Skipping row {row_num} due to invalid coordinates: {row} - {e}"
                            )
                        )
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f"Error: CSV file '{csv_file}' not found")
            )
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading CSV file: {e}"))
            return

        if not coordinates:
            self.stdout.write(
                self.style.ERROR("No valid coordinates found in CSV file")
            )
            return

        self.stdout.write(f"Found {len(coordinates)} valid coordinate pairs")
        
        # Generate activity types based on options
        activities = []
        if read_activity_from_csv:
            activities = csv_activities
            self.stdout.write("Using activity types from CSV file")
        elif randomize_activities:
            activities = self.generate_random_activities(
                len(coordinates), min_segment_length, max_segment_length
            )
            self.stdout.write("Generated random activity types with clustering")
        else:
            activities = [activity_type] * len(coordinates)
            self.stdout.write(f"Using single activity type: {activity_type}")
            
        # Show activity sequence summary if randomized or from CSV
        if randomize_activities or read_activity_from_csv:
            activity_summary = {}
            for act in activities:
                if act:  # Skip None values
                    activity_summary[act] = activity_summary.get(act, 0) + 1
            self.stdout.write(f"Activity distribution: {activity_summary}")

        # Create Location records
        locations_created = 0

        for i, (lat, lon) in enumerate(coordinates):
            try:
                # Calculate timestamp for this location
                location_time = start_time + (i * interval)

                # Create GPS point and transform to local coordinates
                gps_point = Point(lon, lat, srid=4326)
                gps_point.transform(gps_to_local)
                
                # Get activity type for this location
                current_activity = activities[i] if activities[i] is not None else activity_type

                # Create Location record
                location = Location(
                    time=location_time,
                    uuid=device_uuid,
                    loc=gps_point,
                    loc_error=location_error,
                    atype=current_activity,
                    aconf=activity_confidence,
                    speed=speed,
                    speed_error=speed_error,
                    created_at=location_time,
                    debug=False,
                )

                # Save to database
                location.save()
                locations_created += 1

                self.stdout.write(
                    f"Created location {i+1}/{len(coordinates)}: "
                    f"({lat:.6f}, {lon:.6f}) at {location_time} "
                    f"activity: {current_activity} "
                    f"(error: {location_error}, confidence: {activity_confidence}, "
                    f"speed: {speed} m/s, speed_error: {speed_error})"
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error creating location {i+1}: {e}")
                )
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {locations_created} location records"
            )
        )
