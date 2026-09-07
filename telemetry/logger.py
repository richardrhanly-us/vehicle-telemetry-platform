import json
from datetime import datetime
from pathlib import Path


TRIPS_DIR = Path("data") / "trips"


def create_trip_files():
    TRIPS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    trip_file = TRIPS_DIR / f"trip_{timestamp}.jsonl"
    metadata_file = (
        TRIPS_DIR
        / f"trip_{timestamp}_metadata.json"
    )

    return trip_file, metadata_file


def log_sample(file_path, sample):
    with open(
        file_path,
        "a",
        encoding="utf-8",
    ) as file:
        json.dump(sample.to_dict(), file)
        file.write("\n")


def write_trip_metadata(
    file_path,
    start_time,
    end_time,
    sample_count,
    max_rpm,
    max_speed_mph,
    total_rpm,
    total_speed_mph,
    total_sample_duration_ms,
    total_sample_rate_hz,
    sample_rate_count,
    total_missing_values,
    total_query_failures,
    vehicle=None,
    distance_miles=0.0,
    moving_time_seconds=0.0,
    stopped_time_seconds=0.0,
):
    duration_seconds = (
        end_time - start_time
    ).total_seconds()

    average_rpm = (
        round(total_rpm / sample_count, 1)
        if sample_count > 0
        else None
    )

    average_speed_mph = (
        round(
            total_speed_mph / sample_count,
            1,
        )
        if sample_count > 0
        else None
    )

    average_sample_duration_ms = (
        round(
            total_sample_duration_ms
            / sample_count,
            1,
        )
        if sample_count > 0
        else None
    )

    average_sample_rate_hz = (
        round(
            total_sample_rate_hz
            / sample_rate_count,
            2,
        )
        if sample_rate_count > 0
        else None
    )

    average_moving_speed_mph = (
        round(
            distance_miles
            / (moving_time_seconds / 3600),
            1,
        )
        if moving_time_seconds > 0
        else None
    )

    vehicle_data = None

    if vehicle is not None:
        vehicle_data = {
            "year": vehicle.year,
            "make": vehicle.make,
            "model": vehicle.model,
        }

    metadata = {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": round(
            duration_seconds,
            1,
        ),
        "moving_time_seconds": round(
            moving_time_seconds,
            1,
        ),
        "stopped_time_seconds": round(
            stopped_time_seconds,
            1,
        ),
        "distance_miles": round(
            distance_miles,
            2,
        ),
        "average_moving_speed_mph":
            average_moving_speed_mph,
        "sample_count": sample_count,
        "vehicle": vehicle_data,
        "max_rpm": max_rpm,
        "max_speed_mph": max_speed_mph,
        "average_rpm": average_rpm,
        "average_speed_mph": average_speed_mph,
        "average_sample_duration_ms":
            average_sample_duration_ms,
        "average_sample_rate_hz":
            average_sample_rate_hz,
        "total_missing_values":
            total_missing_values,
        "total_query_failures":
            total_query_failures,
    }

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=4,
        )