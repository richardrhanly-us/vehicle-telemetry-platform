import json
from pathlib import Path

import obd
import requests

from telemetry.models import VehicleInfo


PROFILE_FILE = Path("vehicle_profiles.json")


def get_vehicle_vin(connection):
    if not connection.supports(obd.commands.VIN):
        return None

    response = connection.query(obd.commands.VIN)

    if response.is_null():
        return None

    vin = response.value

    if isinstance(vin, (bytes, bytearray)):
        vin = vin.decode("ascii")

    return str(vin).strip()


def decode_vehicle_vin(vin):
    url = (
        "https://vpic.nhtsa.dot.gov/api/vehicles/"
        f"DecodeVinValues/{vin}?format=json"
    )

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()
        result = data["Results"][0]

        return VehicleInfo(
            vin=vin,
            year=result.get("ModelYear") or None,
            make=result.get("Make") or None,
            model=result.get("Model") or None,
        )

    except (
        requests.RequestException,
        KeyError,
        IndexError,
        ValueError,
    ):
        return VehicleInfo(
            vin=vin,
            year=None,
            make=None,
            model=None,
        )


def normalize_fingerprint_value(value):
    if value is None:
        return None

    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("ascii").strip()
        except UnicodeDecodeError:
            return value.hex()

    if isinstance(value, (list, tuple, set)):
        return [
            normalize_fingerprint_value(item)
            for item in value
        ]

    return str(value).strip()


def query_fingerprint_command(connection, command):
    if not connection.supports(command):
        return None

    try:
        response = connection.query(command)

        if response.is_null():
            return None

        return normalize_fingerprint_value(response.value)

    except Exception:
        return None


def get_supported_command_names(connection):
    command_names = []

    for command in connection.supported_commands:
        name = getattr(command, "name", None)

        if name:
            command_names.append(name)

    return sorted(command_names)


def build_vehicle_fingerprint(connection):
    calibration_id = query_fingerprint_command(
        connection,
        obd.commands.CALIBRATION_ID,
    )

    cvn = query_fingerprint_command(
        connection,
        obd.commands.CVN,
    )

    fingerprint = {
        "protocol_id": connection.protocol_id(),
        "protocol_name": connection.protocol_name(),
        "calibration_id": calibration_id,
        "cvn": cvn,
        "supported_commands": get_supported_command_names(
            connection
        ),
    }

    return fingerprint


def load_vehicle_profiles():
    if not PROFILE_FILE.exists():
        return []

    try:
        with open(
            PROFILE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data.get("profiles", [])

    except (OSError, json.JSONDecodeError):
        return []


def save_vehicle_profiles(profiles):
    data = {
        "profiles": profiles
    }

    with open(
        PROFILE_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(data, file, indent=4)


def fingerprints_match(saved, current):
    if not saved or not current:
        return False

    saved_calibration = saved.get("calibration_id")
    current_calibration = current.get("calibration_id")

    saved_cvn = saved.get("cvn")
    current_cvn = current.get("cvn")

    if (
        saved_calibration
        and current_calibration
        and saved_cvn
        and current_cvn
    ):
        return (
            saved_calibration == current_calibration
            and saved_cvn == current_cvn
            and saved.get("protocol_id")
            == current.get("protocol_id")
        )

    saved_commands = saved.get(
        "supported_commands",
        [],
    )

    current_commands = current.get(
        "supported_commands",
        [],
    )

    if not saved_commands or not current_commands:
        return False

    return (
        saved.get("protocol_id")
        == current.get("protocol_id")
        and saved_commands == current_commands
    )


def find_matching_profile(profiles, fingerprint):
    matches = []

    for index, profile in enumerate(profiles):
        saved_fingerprint = profile.get("fingerprint")

        if fingerprints_match(
            saved_fingerprint,
            fingerprint,
        ):
            matches.append((index, profile))

    if len(matches) == 1:
        return matches[0]

    return None


def profile_to_vehicle_info(profile):
    return VehicleInfo(
        vin=profile.get("vin"),
        year=profile.get("year"),
        make=profile.get("make"),
        model=profile.get("model"),
    )


def create_vehicle_profile(fingerprint):
    print()
    print("Create new vehicle profile")
    print("--------------------------")

    name = input("Profile name: ").strip()
    year = input("Year: ").strip()
    make = input("Make: ").strip()
    model = input("Model: ").strip()

    profile = {
        "name": name,
        "vin": None,
        "year": year,
        "make": make,
        "model": model,
        "fingerprint": fingerprint,
    }

    profiles = load_vehicle_profiles()
    profiles.append(profile)

    save_vehicle_profiles(profiles)

    print()
    print(f'Vehicle profile "{name}" saved.')
    print("Vehicle fingerprint saved for automatic detection.")

    return profile_to_vehicle_info(profile)


def choose_vehicle_profile(fingerprint):
    profiles = load_vehicle_profiles()

    if not profiles:
        print()
        print("VIN could not be detected.")
        print("No saved vehicle profiles found.")

        return create_vehicle_profile(
            fingerprint
        )

    print()
    print("VIN could not be detected.")
    print()
    print("Saved vehicle profiles:")

    for index, profile in enumerate(
        profiles,
        start=1,
    ):
        print(
            f"{index}. "
            f"{profile['name']} - "
            f"{profile['year']} "
            f"{profile['make']} "
            f"{profile['model']}"
        )

    new_profile_option = len(profiles) + 1

    print(
        f"{new_profile_option}. "
        "Create new vehicle profile"
    )

    while True:
        choice = input("Select vehicle: ").strip()

        try:
            choice = int(choice)

        except ValueError:
            print("Please enter a number.")
            continue

        if choice == new_profile_option:
            return create_vehicle_profile(
                fingerprint
            )

        if 1 <= choice <= len(profiles):
            profile_index = choice - 1
            profile = profiles[profile_index]

            profile["fingerprint"] = fingerprint

            profiles[profile_index] = profile

            save_vehicle_profiles(profiles)

            print()
            print(
                f'Vehicle profile '
                f'"{profile["name"]}" selected.'
            )
            print(
                "Vehicle fingerprint saved "
                "for automatic detection."
            )

            return profile_to_vehicle_info(profile)

        print("Invalid selection.")


def identify_vehicle(
    connection,
    allow_profile_prompt=True,
):
    vin = get_vehicle_vin(connection)

    if vin is not None:
        vehicle = decode_vehicle_vin(vin)

        if (
            vehicle.year
            and vehicle.make
            and vehicle.model
        ):
            print("Vehicle identified by VIN.")
            return vehicle

        print(
            "VIN detected, but vehicle details "
            "could not be decoded."
        )

    fingerprint = build_vehicle_fingerprint(
        connection
    )

    profiles = load_vehicle_profiles()

    match = find_matching_profile(
        profiles,
        fingerprint,
    )

    if match is not None:
        _, profile = match

        print()
        print(
            "Vehicle fingerprint matched "
            "saved profile."
        )

        return profile_to_vehicle_info(profile)

    if not allow_profile_prompt:
        print(
            "Vehicle detected, but no saved "
            "profile matched automatically."
        )
        return None

    return choose_vehicle_profile(
        fingerprint
    )
