import asyncio
import json
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

import telemetry.runtime_state as runtime_state
from telemetry.trip_controller import trip_controller

app = FastAPI()

DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"
TRIPS_PAGE_FILE = Path(__file__).parent / "trips.html"
TRIPS_DIR = Path("data") / "trips"


def get_trip_id(metadata_file):
    filename = metadata_file.name
    return filename.removeprefix("trip_").removesuffix("_metadata.json")


def load_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def load_jsonl_file(file_path):
    items = []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []

    return items


def load_trip_samples(file_path):
    return load_jsonl_file(file_path)


def load_trip_events(file_path):
    return load_jsonl_file(file_path)


def build_trip_summary(trip_id, metadata):
    vehicle = metadata.get("vehicle")

    if vehicle is None:
        vehicle = {
            "year": None,
            "make": None,
            "model": None,
        }

    return {
        "trip_id": trip_id,
        "start_time": metadata.get("start_time"),
        "end_time": metadata.get("end_time"),
        "duration_seconds": metadata.get("duration_seconds"),
        "sample_count": metadata.get("sample_count"),
        "distance_miles": metadata.get("distance_miles"),
        "vehicle": vehicle,
        "max_rpm": metadata.get("max_rpm"),
        "max_speed_mph": metadata.get("max_speed_mph"),
        "average_rpm": metadata.get("average_rpm"),
        "average_speed_mph": metadata.get("average_speed_mph"),
        "average_sample_duration_ms": metadata.get(
            "average_sample_duration_ms"
        ),
        "average_sample_rate_hz": metadata.get(
            "average_sample_rate_hz"
        ),
        "total_missing_values": metadata.get(
            "total_missing_values"
        ),
        "total_query_failures": metadata.get(
            "total_query_failures"
        ),
        "moving_time_seconds": metadata.get(
            "moving_time_seconds"
        ),
        "stopped_time_seconds": metadata.get(
            "stopped_time_seconds"
        ),
        "average_moving_speed_mph": metadata.get(
            "average_moving_speed_mph"
        ),
        "alarm_event_count": metadata.get(
            "alarm_event_count",
            0,
        ),
        "alarm_trigger_count": metadata.get(
            "alarm_trigger_count",
            0,
        ),
        "alarm_clear_count": metadata.get(
            "alarm_clear_count",
            0,
        ),
    }


@app.get("/")
def root():
    return {
        "service": "nominal-telemetry",
        "status": "running",
    }


@app.get("/vehicle")
def vehicle():
    return runtime_state.vehicle_info


@app.get("/dashboard")
def dashboard():
    return FileResponse(DASHBOARD_FILE)


@app.get("/trips")
def trips_page():
    return FileResponse(TRIPS_PAGE_FILE)


@app.get("/api/vehicle/status")
def get_vehicle_status():
    return trip_controller.get_vehicle_status()


@app.post("/api/vehicle/scan")
def scan_vehicle(interactive: bool = False):
    started = trip_controller.scan_vehicle(
        interactive=interactive,
    )

    if not started:
        raise HTTPException(
            status_code=409,
            detail=(
                "Vehicle scan cannot start while "
                "another scan or trip is active."
            ),
        )

    return trip_controller.get_vehicle_status()


@app.get("/api/trip/status")
def get_trip_status():
    return trip_controller.get_status()


@app.post("/api/trip/start")
def start_trip():
    started = trip_controller.start_trip()

    if not started:
        status = trip_controller.get_status()

        if not status["vehicle_ready"]:
            detail = "No vehicle has been identified."
        else:
            detail = (
                "A trip or vehicle scan "
                "is already active."
            )

        raise HTTPException(
            status_code=409,
            detail=detail,
        )

    return trip_controller.get_status()


@app.post("/api/trip/stop")
def stop_trip():
    stopped = trip_controller.stop_trip()

    if not stopped:
        raise HTTPException(
            status_code=409,
            detail="No trip is currently recording.",
        )

    return trip_controller.get_status()


@app.get("/api/trips")
def get_trips():
    if not TRIPS_DIR.exists():
        return []

    trips = []
    metadata_files = TRIPS_DIR.glob(
        "trip_*_metadata.json"
    )

    for metadata_file in metadata_files:
        metadata = load_json_file(metadata_file)

        if metadata is None:
            continue

        trip_id = get_trip_id(metadata_file)

        trip = build_trip_summary(
            trip_id,
            metadata,
        )

        trips.append(trip)

    trips.sort(
        key=lambda trip: (
            trip.get("start_time") or ""
        ),
        reverse=True,
    )

    return trips


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: str):
    if (
        "/" in trip_id
        or "\\" in trip_id
        or ".." in trip_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid trip ID.",
        )

    metadata_file = (
        TRIPS_DIR
        / f"trip_{trip_id}_metadata.json"
    )

    trip_file = (
        TRIPS_DIR
        / f"trip_{trip_id}.jsonl"
    )

    events_file = (
        TRIPS_DIR
        / f"trip_{trip_id}_events.jsonl"
    )

    if not metadata_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Trip not found.",
        )

    metadata = load_json_file(metadata_file)

    if metadata is None:
        raise HTTPException(
            status_code=500,
            detail="Trip metadata could not be read.",
        )

    samples = []
    if trip_file.exists():
        samples = load_trip_samples(trip_file)

    events = []
    if events_file.exists():
        events = load_trip_events(events_file)

    trip_summary = build_trip_summary(
        trip_id,
        metadata,
    )

    trip_summary.pop(
        "trip_id",
        None,
    )

    return {
        "trip_id": trip_id,
        "metadata": trip_summary,
        "samples": samples,
        "events": events,
    }


@app.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    await websocket.accept()

    last_sequence_sent = None

    disconnect_task = asyncio.create_task(
        websocket.receive()
    )

    try:
        while True:
            done, _ = await asyncio.wait(
                {disconnect_task},
                timeout=0.05,
            )

            if disconnect_task in done:
                message = disconnect_task.result()

                if (
                    message["type"]
                    == "websocket.disconnect"
                ):
                    break

                disconnect_task = (
                    asyncio.create_task(
                        websocket.receive()
                    )
                )

            if runtime_state.latest_sample is not None:
                current_sequence = (
                    runtime_state.latest_sample["sequence"]
                )

                if (
                    current_sequence
                    != last_sequence_sent
                ):
                    await websocket.send_json(
                        runtime_state.latest_sample
                    )

                    last_sequence_sent = current_sequence

    except WebSocketDisconnect:
        pass

    finally:
        if not disconnect_task.done():
            disconnect_task.cancel()

            with suppress(
                asyncio.CancelledError
            ):
                await disconnect_task

        print("Telemetry WebSocket closed.")
