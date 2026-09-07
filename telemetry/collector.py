from datetime import datetime, timezone

from time import perf_counter

import os
import obd

from telemetry.logger import (

    create_trip_files,

    log_sample,

    write_trip_metadata,

)

from telemetry.models import TelemetrySample

from telemetry.normalizer import (

    normalize_percent,

    normalize_rpm,

    normalize_speed_mph,

)

from telemetry.vehicle import identify_vehicle



CONNECTION_FAILURE_THRESHOLD = 2
OBD_PORT = os.getenv("OBD_PORT", "COM3")

RPM_COMMAND = getattr(obd.commands, "RPM")
SPEED_COMMAND = getattr(obd.commands, "SPEED")
THROTTLE_COMMAND = getattr(obd.commands, "THROTTLE_POS")
ENGINE_LOAD_COMMAND = getattr(obd.commands, "ENGINE_LOAD")

def connect_to_vehicle():

    print(

        "Connecting to OBD-II adapter "

        f"on {OBD_PORT}..."

    )

    connection = obd.OBD(OBD_PORT)

    print(

        "Connection status:",

        connection.status(),

    )

    return connection



def check_vehicle_connection():

    """

    Lightweight physical presence check.

    Opens the configured OBD port, checks whether python-OBD can

    establish a vehicle connection, then closes

    the connection immediately.

    This does NOT identify the vehicle.

    """

    connection = None

    try:

        connection = obd.OBD(

            "COM3",

            fast=True,

        )

        return connection.is_connected()

    except Exception:

        return False

    finally:

        if connection is not None:

            try:

                connection.close()

            except Exception:

                pass



def scan_for_vehicle(

    allow_profile_prompt=False,

):

    connection = None

    try:

        connection = connect_to_vehicle()

        if not connection.is_connected():

            print(

                "No vehicle detected."

            )

            return None

        vehicle = identify_vehicle(

            connection,

            allow_profile_prompt=

                allow_profile_prompt,

        )

        if vehicle is not None:

            print(

                "Vehicle:",

                vehicle.year,

                vehicle.make,

                vehicle.model,

            )

        return vehicle

    finally:

        if connection is not None:

            connection.close()

            print(

                "Vehicle scan connection closed."

            )



def safe_query(

    connection,

    command,

):

    if not connection.supports(command):

        return None, True

    try:

        response = connection.query(

            command

        )

        if response.is_null():

            return None, True

        return response, False

    except Exception:

        return None, True



def collect_sample(

    connection,

    sequence,

    previous_timestamp,

):

    sample_start = perf_counter()

    timestamp = datetime.now(

        timezone.utc

    )

    rpm_response, rpm_failed = (

        safe_query(

            connection,

            RPM_COMMAND,

        )

    )

    speed_response, speed_failed = (

        safe_query(

            connection,

            SPEED_COMMAND,

        )

    )

    throttle_response, throttle_failed = (

        safe_query(

            connection,

            THROTTLE_COMMAND,

        )

    )

    load_response, load_failed = (

        safe_query(

            connection,

            ENGINE_LOAD_COMMAND,

        )

    )

    rpm = (

        normalize_rpm(rpm_response)

        if rpm_response

        else None

    )

    speed_mph = (

        normalize_speed_mph(

            speed_response

        )

        if speed_response

        else None

    )

    throttle_pct = (

        normalize_percent(

            throttle_response

        )

        if throttle_response

        else None

    )

    load_pct = (

        normalize_percent(

            load_response

        )

        if load_response

        else None

    )

    query_failures = sum(

        [

            rpm_failed,

            speed_failed,

            throttle_failed,

            load_failed,

        ]

    )

    missing_values = sum(

        value is None

        for value in [

            rpm,

            speed_mph,

            throttle_pct,

            load_pct,

        ]

    )

    sample_duration_ms = round(

        (

            perf_counter()

            - sample_start

        )

        * 1000,

        1,

    )

    sample_rate_hz = None

    if previous_timestamp is not None:

        elapsed_seconds = (

            timestamp

            - previous_timestamp

        ).total_seconds()

        if elapsed_seconds > 0:

            sample_rate_hz = round(

                1 / elapsed_seconds,

                2,

            )

    return TelemetrySample(

        sequence=sequence,

        timestamp=timestamp,

        rpm=rpm,

        speed_mph=speed_mph,

        throttle_pct=throttle_pct,

        load_pct=load_pct,

        sample_duration_ms=

            sample_duration_ms,

        sample_rate_hz=sample_rate_hz,

        missing_values=missing_values,

        query_failures=query_failures,

        connection_status=str(

            connection.status()

        ),

    )



def run_collector(

    stop_event,

    vehicle,

    on_sample=None,

):

    connection = None

    try:

        connection = (

            connect_to_vehicle()

        )

        if not connection.is_connected():

            raise RuntimeError(

                "Vehicle is no longer connected."

            )

        trip_file, metadata_file = (

            create_trip_files()

        )

        print(

            "Recording trip to:",

            trip_file,

        )

        start_time = datetime.now(

            timezone.utc

        )

        sequence = 0

        previous_timestamp = None

        previous_speed_mph = None

        distance_miles = 0.0

        moving_time_seconds = 0.0

        stopped_time_seconds = 0.0

        max_rpm = None

        max_speed_mph = None

        total_rpm = 0

        total_speed_mph = 0

        total_sample_duration_ms = 0

        total_sample_rate_hz = 0

        sample_rate_count = 0

        total_missing_values = 0

        total_query_failures = 0

        consecutive_connection_failures = 0

        while not stop_event.is_set():

            sequence += 1

            sample = collect_sample(

                connection,

                sequence,

                previous_timestamp,

            )

            connection_lost = (

                not connection.is_connected()

                or sample.query_failures == 4

            )

            if connection_lost:

                consecutive_connection_failures += (

                    1

                )

            else:

                consecutive_connection_failures = (

                    0

                )

            if (

                consecutive_connection_failures

                >= CONNECTION_FAILURE_THRESHOLD

            ):

                raise RuntimeError(

                    "OBD-II vehicle disconnected."

                )

            if (

                previous_timestamp

                is not None

                and previous_speed_mph

                is not None

                and sample.speed_mph

                is not None

            ):

                elapsed_seconds = (

                    sample.timestamp

                    - previous_timestamp

                ).total_seconds()

                average_segment_speed_mph = (

                    previous_speed_mph

                    + sample.speed_mph

                ) / 2

                distance_miles += (

                    average_segment_speed_mph

                    * (

                        elapsed_seconds

                        / 3600

                    )

                )

                if (

                    average_segment_speed_mph

                    > 0

                ):

                    moving_time_seconds += (

                        elapsed_seconds

                    )

                else:

                    stopped_time_seconds += (

                        elapsed_seconds

                    )

            previous_timestamp = (

                sample.timestamp

            )

            previous_speed_mph = (

                sample.speed_mph

            )

            log_sample(

                trip_file,

                sample,

            )

            if on_sample is not None:

                on_sample(sample)

            total_sample_duration_ms += (

                sample.sample_duration_ms

            )

            if (

                sample.sample_rate_hz

                is not None

            ):

                total_sample_rate_hz += (

                    sample.sample_rate_hz

                )

                sample_rate_count += 1

            total_missing_values += (

                sample.missing_values

            )

            total_query_failures += (

                sample.query_failures

            )

            if sample.rpm is not None:

                total_rpm += sample.rpm

                if (

                    max_rpm is None

                    or sample.rpm

                    > max_rpm

                ):

                    max_rpm = sample.rpm

            if sample.speed_mph is not None:

                total_speed_mph += (

                    sample.speed_mph

                )

                if (

                    max_speed_mph is None

                    or sample.speed_mph

                    > max_speed_mph

                ):

                    max_speed_mph = (

                        sample.speed_mph

                    )

            print(

                f"[{sample.sequence:04}] "

                f"{sample.timestamp.isoformat()} "

                f"RPM="

                f"{sample.rpm if sample.rpm is not None else 'N/A'} "

                f"SPEED_MPH="

                f"{sample.speed_mph if sample.speed_mph is not None else 'N/A'} "

                f"THROTTLE_PCT="

                f"{sample.throttle_pct if sample.throttle_pct is not None else 'N/A'} "

                f"LOAD_PCT="

                f"{sample.load_pct if sample.load_pct is not None else 'N/A'} "

                f"DURATION_MS="

                f"{sample.sample_duration_ms} "

                f"RATE_HZ="

                f"{sample.sample_rate_hz if sample.sample_rate_hz is not None else 'N/A'} "

                f"MISSING="

                f"{sample.missing_values} "

                f"FAILURES="

                f"{sample.query_failures}"

            )

            stop_event.wait(1)

    finally:

        if connection is not None:

            if "start_time" in locals():

                end_time = datetime.now(

                    timezone.utc

                )

                write_trip_metadata(

                    metadata_file,

                    start_time,

                    end_time,

                    sequence,

                    max_rpm,

                    max_speed_mph,

                    total_rpm,

                    total_speed_mph,

                    total_sample_duration_ms,

                    total_sample_rate_hz,

                    sample_rate_count,

                    total_missing_values,

                    total_query_failures,

                    vehicle,

                    distance_miles,

                    moving_time_seconds,

                    stopped_time_seconds,

                )

                print(

                    "Trip metadata saved to:",

                    metadata_file,

                )

            connection.close()

            print(

                "OBD-II connection closed."

            )