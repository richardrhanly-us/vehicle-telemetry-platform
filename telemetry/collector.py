import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from time import perf_counter, sleep

import obd
from dotenv import load_dotenv

from telemetry.alarms import AlarmEngine
from telemetry.logger import (
    create_trip_files,
    log_alarm_event,
    log_sample,
    write_trip_metadata,
)
from telemetry.models import TelemetrySample
from telemetry.normalizer import (
    normalize_mass_air_flow,
    normalize_percent,
    normalize_pressure_kpa,
    normalize_rpm,
    normalize_speed_mph,
    normalize_temperature_f,
    normalize_voltage,
)
from telemetry.vehicle import identify_vehicle


CONNECTION_FAILURE_THRESHOLD = 2
CONNECTION_ATTEMPTS = 3
CONNECTION_RETRY_DELAY_SECONDS = 1.0

load_dotenv()

OBD_PORT = os.getenv("OBD_PORT", "COM3")
ALARM_RULES_PATH = (
    Path(__file__).resolve().parents[1]
    / "alarm_rules.json"
)

RPM_COMMAND = getattr(obd.commands, "RPM")
SPEED_COMMAND = getattr(obd.commands, "SPEED")
THROTTLE_COMMAND = getattr(obd.commands, "THROTTLE_POS")
ENGINE_LOAD_COMMAND = getattr(obd.commands, "ENGINE_LOAD")

COOLANT_TEMP_COMMAND = getattr(
    obd.commands,
    "COOLANT_TEMP",
    None,
)
INTAKE_TEMP_COMMAND = getattr(
    obd.commands,
    "INTAKE_TEMP",
    None,
)
AMBIENT_TEMP_COMMAND = getattr(
    obd.commands,
    "AMBIANT_AIR_TEMP",
    None,
)
OIL_TEMP_COMMAND = getattr(
    obd.commands,
    "OIL_TEMP",
    None,
)
CATALYST_TEMP_B1S1_COMMAND = getattr(
    obd.commands,
    "CATALYST_TEMP_B1S1",
    None,
)
CATALYST_TEMP_B1S2_COMMAND = getattr(
    obd.commands,
    "CATALYST_TEMP_B1S2",
    None,
)
MAF_COMMAND = getattr(
    obd.commands,
    "MAF",
    None,
)
MANIFOLD_PRESSURE_COMMAND = getattr(
    obd.commands,
    "INTAKE_PRESSURE",
    None,
)
MODULE_VOLTAGE_COMMAND = getattr(
    obd.commands,
    "CONTROL_MODULE_VOLTAGE",
    None,
)

OBD_CONNECTION_LOCK = RLock()


def connect_to_vehicle():
    last_connection = None

    for attempt in range(
        1,
        CONNECTION_ATTEMPTS + 1,
    ):
        if attempt == 1:
            print(
                f"Connecting to OBD-II adapter on {OBD_PORT}..."
            )
        else:
            print(
                "Retrying OBD-II connection "
                f"({attempt}/{CONNECTION_ATTEMPTS})..."
            )

        connection = obd.OBD(OBD_PORT)

        print(
            "Connection status:",
            connection.status(),
        )

        if connection.is_connected():
            return connection

        last_connection = connection

        if attempt < CONNECTION_ATTEMPTS:
            connection.close()
            last_connection = None
            sleep(
                CONNECTION_RETRY_DELAY_SECONDS
            )

    if last_connection is not None:
        return last_connection

    return obd.OBD(OBD_PORT)


def check_vehicle_connection():
    """
    Lightweight physical presence check.

    Opens the configured OBD port, checks whether python-OBD can
    establish a vehicle connection, then closes the connection
    immediately.

    This does NOT identify the vehicle.
    """

    connection = None

    with OBD_CONNECTION_LOCK:
        try:
            connection = obd.OBD(
                OBD_PORT,
                fast=True,
            )
            return connection.is_connected()

        except Exception:  # noqa: BLE001
            return False

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:  # noqa: BLE001
                    pass


def scan_for_vehicle(
    allow_profile_prompt=False,
):
    connection = None

    with OBD_CONNECTION_LOCK:
        try:
            connection = connect_to_vehicle()

            if not connection.is_connected():
                print("No vehicle detected.")
                return None

            vehicle = identify_vehicle(
                connection,
                allow_profile_prompt=allow_profile_prompt,
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
        response = connection.query(command)

        if response.is_null():
            return None, True

        return response, False

    except Exception:  # noqa: BLE001
        return None, True


def safe_optional_query(
    connection,
    command,
):
    if command is None:
        return None

    try:
        if not connection.supports(command):
            return None

        response = connection.query(command)

        if response.is_null():
            return None

        return response

    except Exception:  # noqa: BLE001
        return None


def collect_sample(
    connection,
    sequence,
    previous_timestamp,
):
    sample_start = perf_counter()
    timestamp = datetime.now(timezone.utc)

    rpm_response, rpm_failed = safe_query(
        connection,
        RPM_COMMAND,
    )
    speed_response, speed_failed = safe_query(
        connection,
        SPEED_COMMAND,
    )
    throttle_response, throttle_failed = safe_query(
        connection,
        THROTTLE_COMMAND,
    )
    load_response, load_failed = safe_query(
        connection,
        ENGINE_LOAD_COMMAND,
    )

    coolant_response = safe_optional_query(
        connection,
        COOLANT_TEMP_COMMAND,
    )
    intake_temp_response = safe_optional_query(
        connection,
        INTAKE_TEMP_COMMAND,
    )
    ambient_temp_response = safe_optional_query(
        connection,
        AMBIENT_TEMP_COMMAND,
    )
    oil_temp_response = safe_optional_query(
        connection,
        OIL_TEMP_COMMAND,
    )
    catalyst_temp_b1s1_response = safe_optional_query(
        connection,
        CATALYST_TEMP_B1S1_COMMAND,
    )
    catalyst_temp_b1s2_response = safe_optional_query(
        connection,
        CATALYST_TEMP_B1S2_COMMAND,
    )
    maf_response = safe_optional_query(
        connection,
        MAF_COMMAND,
    )
    manifold_pressure_response = safe_optional_query(
        connection,
        MANIFOLD_PRESSURE_COMMAND,
    )
    module_voltage_response = safe_optional_query(
        connection,
        MODULE_VOLTAGE_COMMAND,
    )

    rpm = (
        normalize_rpm(rpm_response)
        if rpm_response
        else None
    )
    speed_mph = (
        normalize_speed_mph(speed_response)
        if speed_response
        else None
    )
    throttle_pct = (
        normalize_percent(throttle_response)
        if throttle_response
        else None
    )
    load_pct = (
        normalize_percent(load_response)
        if load_response
        else None
    )
    coolant_temp_f = (
        normalize_temperature_f(
            coolant_response
        )
        if coolant_response
        else None
    )
    intake_temp_f = (
        normalize_temperature_f(
            intake_temp_response
        )
        if intake_temp_response
        else None
    )
    ambient_temp_f = (
        normalize_temperature_f(
            ambient_temp_response
        )
        if ambient_temp_response
        else None
    )
    oil_temp_f = (
        normalize_temperature_f(
            oil_temp_response
        )
        if oil_temp_response
        else None
    )
    catalyst_temp_b1s1_f = (
        normalize_temperature_f(
            catalyst_temp_b1s1_response
        )
        if catalyst_temp_b1s1_response
        else None
    )
    catalyst_temp_b1s2_f = (
        normalize_temperature_f(
            catalyst_temp_b1s2_response
        )
        if catalyst_temp_b1s2_response
        else None
    )
    maf_gps = (
        normalize_mass_air_flow(
            maf_response
        )
        if maf_response
        else None
    )
    manifold_pressure_kpa = (
        normalize_pressure_kpa(
            manifold_pressure_response
        )
        if manifold_pressure_response
        else None
    )
    module_voltage_v = (
        normalize_voltage(
            module_voltage_response
        )
        if module_voltage_response
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
        (perf_counter() - sample_start)
        * 1000,
        1,
    )

    sample_rate_hz = None

    if previous_timestamp is not None:
        elapsed_seconds = (
            timestamp - previous_timestamp
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
        coolant_temp_f=coolant_temp_f,
        intake_temp_f=intake_temp_f,
        ambient_temp_f=ambient_temp_f,
        oil_temp_f=oil_temp_f,
        catalyst_temp_b1s1_f=catalyst_temp_b1s1_f,
        catalyst_temp_b1s2_f=catalyst_temp_b1s2_f,
        maf_gps=maf_gps,
        manifold_pressure_kpa=(
            manifold_pressure_kpa
        ),
        module_voltage_v=module_voltage_v,
        sample_duration_ms=sample_duration_ms,
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
    on_alarm=None,
):
    with OBD_CONNECTION_LOCK:
        connection = None

        try:
            connection = connect_to_vehicle()

            if not connection.is_connected():
                raise RuntimeError(
                    "Vehicle is no longer connected."
                )

            alarm_engine = (
                AlarmEngine.from_json_file(
                    ALARM_RULES_PATH
                )
            )

            print(
                f"Loaded {len(alarm_engine.rules)} alarm rules."
            )

            (
                trip_file,
                metadata_file,
                events_file,
            ) = create_trip_files()

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
            alarm_event_count = 0
            alarm_trigger_count = 0
            alarm_clear_count = 0
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
                    consecutive_connection_failures += 1
                else:
                    consecutive_connection_failures = 0

                if (
                    consecutive_connection_failures
                    >= CONNECTION_FAILURE_THRESHOLD
                ):
                    raise RuntimeError(
                        "OBD-II vehicle disconnected."
                    )

                if sample.query_failures < 4:
                    alarm_events = (
                        alarm_engine.evaluate(
                            sample
                        )
                    )

                    for event in alarm_events:
                        log_alarm_event(
                            events_file,
                            event,
                        )
                        alarm_event_count += 1

                        if (
                            event["type"]
                            == "triggered"
                        ):
                            alarm_trigger_count += 1
                        elif (
                            event["type"]
                            == "cleared"
                        ):
                            alarm_clear_count += 1

                        print(
                            f"[ALARM "
                            f"{event['type'].upper()}] "
                            f"{event['severity'].upper()} "
                            f"{event['rule']} "
                            f"value={event['value']} "
                            f"threshold="
                            f"{event['operator']}"
                            f"{event['threshold']}"
                        )

                        if on_alarm is not None:
                            on_alarm(event)

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
                        or sample.rpm > max_rpm
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
                    f"COOLANT_F="
                    f"{sample.coolant_temp_f if sample.coolant_temp_f is not None else 'N/A'} "
                    f"INTAKE_F="
                    f"{sample.intake_temp_f if sample.intake_temp_f is not None else 'N/A'} "
                    f"AMBIENT_F="
                    f"{sample.ambient_temp_f if sample.ambient_temp_f is not None else 'N/A'} "
                    f"OIL_F="
                    f"{sample.oil_temp_f if sample.oil_temp_f is not None else 'N/A'} "
                    f"CAT_B1S1_F="
                    f"{sample.catalyst_temp_b1s1_f if sample.catalyst_temp_b1s1_f is not None else 'N/A'} "
                    f"CAT_B1S2_F="
                    f"{sample.catalyst_temp_b1s2_f if sample.catalyst_temp_b1s2_f is not None else 'N/A'} "
                    f"MAF_GPS="
                    f"{sample.maf_gps if sample.maf_gps is not None else 'N/A'} "
                    f"MAP_KPA="
                    f"{sample.manifold_pressure_kpa if sample.manifold_pressure_kpa is not None else 'N/A'} "
                    f"VOLTAGE_V="
                    f"{sample.module_voltage_v if sample.module_voltage_v is not None else 'N/A'} "
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
                        alarm_event_count,
                        alarm_trigger_count,
                        alarm_clear_count,
                    )

                    print(
                        "Trip metadata saved to:",
                        metadata_file,
                    )

                connection.close()
                print(
                    "OBD-II connection closed."
                )
