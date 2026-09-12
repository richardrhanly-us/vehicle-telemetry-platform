import re
import time
from collections import Counter
from pathlib import Path

import serial


PORT = "COM3"

START_BAUDRATES = [
    115_200,
    2_000_000,
]

NORMAL_BAUDRATE = 115_200
CAPTURE_BAUDRATE = 2_000_000

SECONDS_PER_RANGE = 1.5

OUTPUT_DIR = Path("data") / "can"
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "can_id_survey.txt"
)


CAN_RANGES = [
    ("000-0FF", "0000", "0700"),
    ("100-1FF", "0100", "0700"),
    ("200-2FF", "0200", "0700"),
    ("300-3FF", "0300", "0700"),
    ("400-4FF", "0400", "0700"),
    ("500-5FF", "0500", "0700"),
    ("600-6FF", "0600", "0700"),
    ("700-7FF", "0700", "0700"),
]


def read_until_prompt(
    ser: serial.Serial,
    timeout: float = 5.0,
) -> str:
    response = bytearray()

    start = time.monotonic()

    while (
        time.monotonic() - start
        < timeout
    ):
        waiting = ser.in_waiting

        if waiting:
            response.extend(
                ser.read(waiting)
            )

            if b">" in response:
                break

        time.sleep(0.01)

    return response.decode(
        "ascii",
        errors="ignore",
    )


def send_command(
    ser: serial.Serial,
    command: str,
    timeout: float = 5.0,
) -> str:
    ser.reset_input_buffer()

    ser.write(
        (
            command + "\r"
        ).encode("ascii")
    )

    ser.flush()

    response = read_until_prompt(
        ser,
        timeout=timeout,
    )

    cleaned = (
        response
        .replace(">", "")
        .strip()
    )

    print()
    print(f"> {command}")

    if cleaned:
        print(cleaned)
    else:
        print("(no response)")

    return cleaned


def find_adapter_baud() -> tuple[
    serial.Serial,
    int,
]:
    for baudrate in START_BAUDRATES:
        print(
            f"Trying {PORT} at "
            f"{baudrate} baud..."
        )

        ser = serial.Serial(
            PORT,
            baudrate,
            timeout=0.1,
        )

        time.sleep(0.3)

        ser.reset_input_buffer()

        ser.write(b"STI\r")
        ser.flush()

        response = read_until_prompt(
            ser,
            timeout=1.5,
        )

        if response.strip():
            print(
                "Adapter responded at "
                f"{baudrate} baud."
            )

            return ser, baudrate

        ser.close()

    raise RuntimeError(
        "Could not communicate with "
        f"the OBDLink on {PORT}."
    )


def reset_adapter(
    ser: serial.Serial,
) -> None:
    print()
    print("Resetting adapter...")

    ser.reset_input_buffer()

    ser.write(b"ATZ\r")
    ser.flush()

    # The adapter may change baud as
    # part of the reset, so don't try
    # to fully parse the response here.
    time.sleep(1.0)

    # ATZ restores the normal UART rate.
    ser.baudrate = NORMAL_BAUDRATE

    time.sleep(0.5)

    ser.reset_input_buffer()

    response = send_command(
        ser,
        "STI",
        timeout=3.0,
    )

    if not response:
        raise RuntimeError(
            "Adapter did not respond at "
            "115200 baud after reset."
        )

    print()
    print(
        "Adapter reset complete at "
        f"{NORMAL_BAUDRATE} baud."
    )


def switch_to_capture_baud(
    ser: serial.Serial,
) -> None:
    if (
        ser.baudrate
        == CAPTURE_BAUDRATE
    ):
        return

    print()
    print(
        "Switching serial link to "
        f"{CAPTURE_BAUDRATE} baud..."
    )

    ser.reset_input_buffer()

    ser.write(
        (
            f"STSBR "
            f"{CAPTURE_BAUDRATE}\r"
        ).encode("ascii")
    )

    ser.flush()

    time.sleep(0.25)

    old_response = (
        ser.read_all()
        .decode(
            "ascii",
            errors="ignore",
        )
        .strip()
    )

    if old_response:
        print(old_response)

    ser.baudrate = (
        CAPTURE_BAUDRATE
    )

    time.sleep(0.4)

    ser.reset_input_buffer()

    response = send_command(
        ser,
        "STI",
        timeout=3.0,
    )

    if not response:
        raise RuntimeError(
            "Adapter did not respond "
            "after switching to "
            "2 Mbps."
        )

    print()
    print(
        "Serial link now running at "
        f"{CAPTURE_BAUDRATE} baud."
    )


def extract_can_id(
    line: str,
) -> str | None:
    cleaned = (
        line
        .replace(" ", "")
        .upper()
    )

    match = re.match(
        r"^([0-7][0-9A-F]{2})"
        r"[0-9A-F]+$",
        cleaned,
    )

    if not match:
        return None

    return match.group(1)


def monitor_range(
    ser: serial.Serial,
    duration: float,
) -> Counter:
    counts = Counter()

    ser.reset_input_buffer()

    ser.write(b"STM\r")
    ser.flush()

    start = time.monotonic()

    receive_buffer = ""

    while (
        time.monotonic() - start
        < duration
    ):
        waiting = ser.in_waiting

        if not waiting:
            time.sleep(0.001)
            continue

        data = (
            ser.read(waiting)
            .decode(
                "ascii",
                errors="ignore",
            )
        )

        receive_buffer += data

        while "\r" in receive_buffer:
            (
                line,
                receive_buffer,
            ) = receive_buffer.split(
                "\r",
                1,
            )

            line = line.strip()

            if not line:
                continue

            upper_line = line.upper()

            if "BUFFER FULL" in upper_line:
                print(
                    "  WARNING: "
                    "BUFFER FULL"
                )
                continue

            if "STOPPED" in upper_line:
                continue

            can_id = extract_can_id(
                line
            )

            if can_id is not None:
                counts[can_id] += 1

    # Stop monitoring.
    ser.write(b"\r")
    ser.flush()

    read_until_prompt(
        ser,
        timeout=2.0,
    )

    return counts


ser, detected_baudrate = (
    find_adapter_baud()
)

try:
    print()
    print(
        f"Connected to {PORT} "
        f"at {detected_baudrate} baud."
    )

    # Reset the adapter, then deliberately
    # return host communication to 115200.
    reset_adapter(ser)

    # Basic terminal formatting.
    send_command(ser, "ATE0")
    send_command(ser, "ATL0")
    send_command(ser, "ATS0")
    send_command(ser, "ATH1")

    # Automatic vehicle protocol detection.
    send_command(
        ser,
        "ATSP0",
    )

    obd_response = send_command(
        ser,
        "0100",
        timeout=10.0,
    )

    if (
        not obd_response
        or
        "NO DATA"
        in obd_response.upper()
        or
        "UNABLE TO CONNECT"
        in obd_response.upper()
    ):
        raise RuntimeError(
            "Could not establish "
            "vehicle communication."
        )

    print()
    print(
        "Vehicle connection established."
    )
    
    protocol = send_command(
        ser,
        "ATDP",
    )

    # Explicitly select ISO 15765-4 CAN 11-bit / 500 kbit.
    send_command(
        ser,
        "ATSP6",
    )

    # Disable CAN auto formatting so raw CAN frames
    # are returned instead of ISO-15765 interpretation.
    send_command(
        ser,
        "ATCAF0",
    )

    # Keep headers visible so we retain CAN IDs.
    send_command(
        ser,
        "ATH1",
    )

    # Use variable DLC so raw frames are not padded
    # by the adapter.
    send_command(
        ser,
        "ATV1",
    )

    # Now increase host serial speed
    # before raw CAN monitoring.
    switch_to_capture_baud(
        ser
    )

    send_command(ser, "ATS0")
    send_command(ser, "ATH1")

    # Receive-only CAN monitoring.
    send_command(
        ser,
        "STCMM 0",
    )
    
    # Open the CAN hardware filter so every
    # 11-bit CAN ID can reach the ST filters.
    send_command(
        ser,
        "ATCF 000",
    )

    send_command(
        ser,
        "ATCM 000",
    )

    print()
    print(
        "================================"
    )
    print(
        "11-BIT CAN ID SURVEY"
    )
    print(
        "================================"
    )
    print(
        f"Protocol: {protocol}"
    )
    print(
        "Monitoring each range for "
        f"{SECONDS_PER_RANGE} seconds."
    )
    print()

    all_counts = Counter()

    results = []

    for (
        range_name,
        pattern,
        mask,
    ) in CAN_RANGES:
        print(
            f"Scanning {range_name}..."
        )

        send_command(
            ser,
            "STFAC",
        )

        filter_response = (
            send_command(
                ser,
                (
                    f"STFPA "
                    f"{pattern},"
                    f"{mask}"
                ),
            )
        )

        if (
            "OK"
            not in filter_response.upper()
        ):
            print(
                "  Filter rejected."
            )

            results.append(
                (
                    range_name,
                    Counter(),
                )
            )

            continue

        counts = monitor_range(
            ser,
            SECONDS_PER_RANGE,
        )

        results.append(
            (
                range_name,
                counts,
            )
        )

        all_counts.update(
            counts
        )

        if not counts:
            print(
                "  No CAN IDs seen."
            )

        else:
            ids = sorted(
                counts,
                key=lambda value: int(
                    value,
                    16,
                ),
            )

            print(
                "  IDs: "
                + ", ".join(ids)
            )

            print(
                "  Frames: "
                f"{sum(counts.values())}"
            )

        print()

    print()
    print(
        "================================"
    )
    print(
        "SURVEY SUMMARY"
    )
    print(
        "================================"
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as output:
        output.write(
            "11-bit CAN ID survey\n"
        )

        output.write(
            f"Protocol: {protocol}\n\n"
        )

        for (
            range_name,
            counts,
        ) in results:
            output.write(
                f"{range_name}\n"
            )

            if not counts:
                output.write(
                    "  none\n\n"
                )

                continue

            for can_id in sorted(
                counts,
                key=lambda value: int(
                    value,
                    16,
                ),
            ):
                output.write(
                    f"  {can_id}: "
                    f"{counts[can_id]}"
                    "\n"
                )

            output.write("\n")

        output.write(
            "All unique IDs:\n"
        )

        for can_id in sorted(
            all_counts,
            key=lambda value: int(
                value,
                16,
            ),
        ):
            output.write(
                f"  {can_id}: "
                f"{all_counts[can_id]}"
                "\n"
            )

    if all_counts:
        for can_id in sorted(
            all_counts,
            key=lambda value: int(
                value,
                16,
            ),
        ):
            print(
                f"{can_id}: "
                f"{all_counts[can_id]} "
                "frames"
            )

    else:
        print(
            "No CAN IDs discovered."
        )

    print()
    print(
        "Survey saved to:"
    )
    print(
        OUTPUT_FILE
    )

finally:
    ser.close()

    print()
    print(
        "Serial connection closed."
    )