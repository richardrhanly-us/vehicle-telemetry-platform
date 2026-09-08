import json
import threading
from dataclasses import fields
from datetime import datetime
from pathlib import Path

from telemetry import runtime_state
from telemetry.alarms import AlarmEngine
from telemetry.models import TelemetrySample


TRIPS_DIR = Path("data") / "trips"
ALARM_RULES_PATH = (
    Path(__file__).resolve().parents[1]
    / "alarm_rules.json"
)

MIN_PLAYBACK_SPEED = 0.25
MAX_PLAYBACK_SPEED = 10.0


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


def sample_from_dict(sample_data):
    allowed_fields = {
        field.name
        for field in fields(TelemetrySample)
    }

    filtered = {
        key: value
        for key, value in sample_data.items()
        if key in allowed_fields
    }

    timestamp = filtered.get("timestamp")

    if isinstance(timestamp, str):
        filtered["timestamp"] = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )

    return TelemetrySample(**filtered)


class PlaybackController:

    def __init__(self):
        self._lock = threading.RLock()
        self._thread = None
        self._stop_event: threading.Event | None = None

        self._state = "idle"
        self._trip_id = None
        self._speed = 1.0
        self._current_index = 0
        self._sample_count = 0
        self._last_error = None
        self._recording_start_time = None
        self._elapsed_seconds = 0.0
        self._duration_seconds = 0.0

    def is_active(self):
        with self._lock:
            return self._state in {
                "playing",
                "paused",
                "stopping",
            }

    def get_status(self):
        with self._lock:
            return {
                "state": self._state,
                "active": self._state in {
                    "playing",
                    "paused",
                    "stopping",
                },
                "playing": self._state == "playing",
                "paused": self._state == "paused",
                "trip_id": self._trip_id,
                "speed": self._speed,
                "current_index": self._current_index,
                "sample_count": self._sample_count,
                "error": self._last_error,
                "start_time": self._recording_start_time,
                "elapsed_seconds": self._elapsed_seconds,
                "duration_seconds": self._duration_seconds,
            }

    def start(self, trip_id, speed=1.0):
        speed = float(speed)

        if not (
            MIN_PLAYBACK_SPEED <= speed <= MAX_PLAYBACK_SPEED
        ):
            return False

        with self._lock:
            if self._state != "idle":
                return False

            trip_file = TRIPS_DIR / f"trip_{trip_id}.jsonl"
            metadata_file = (
                TRIPS_DIR
                / f"trip_{trip_id}_metadata.json"
            )

            if (
                not trip_file.exists()
                or not metadata_file.exists()
            ):
                return False

            self._trip_id = trip_id
            self._speed = speed
            self._current_index = 0
            self._sample_count = 0
            self._last_error = None
            self._recording_start_time = None
            self._elapsed_seconds = 0.0
            self._duration_seconds = 0.0
            self._state = "playing"
            self._stop_event = threading.Event()

            self._thread = threading.Thread(
                target=self._run_playback,
                args=(trip_file, metadata_file),
                daemon=True,
            )

            self._thread.start()
            return True

    def pause(self):
        with self._lock:
            if self._state != "playing":
                return False

            self._state = "paused"
            return True

    def resume(self):
        with self._lock:
            if self._state != "paused":
                return False

            self._state = "playing"
            return True

    def stop(self):
        with self._lock:
            if self._state not in {"playing", "paused"}:
                return False

            self._state = "stopping"

            if self._stop_event is not None:
                self._stop_event.set()

            return True

    def set_speed(self, speed):
        speed = float(speed)

        if not (
            MIN_PLAYBACK_SPEED <= speed <= MAX_PLAYBACK_SPEED
        ):
            return False

        with self._lock:
            if self._state not in {"playing", "paused"}:
                return False

            self._speed = speed
            return True

    def _wait_while_paused(self):
        while True:
            with self._lock:
                state = self._state
                stop_event = self._stop_event

            if state != "paused":
                return

            if stop_event is not None and stop_event.wait(0.1):
                return

    def _run_playback(self, trip_file, metadata_file):
        try:
            samples = load_jsonl_file(trip_file)
            metadata = load_json_file(metadata_file)

            if not samples:
                raise RuntimeError(
                    "Recorded trip has no samples."
                )

            if metadata is None:
                raise RuntimeError(
                    "Trip metadata could not be read."
                )

            first_sample = sample_from_dict(
                samples[0]
            )

            last_sample = sample_from_dict(
                samples[-1]
            )

            recorded_duration = metadata.get(
                "duration_seconds"
            )

            if recorded_duration is None:
                recorded_duration = max(
                    0.0,
                    (
                        last_sample.timestamp
                        - first_sample.timestamp
                    ).total_seconds(),
                )

            with self._lock:
                self._sample_count = len(samples)
                self._recording_start_time = metadata.get(
                    "start_time"
                )
                self._elapsed_seconds = 0.0
                self._duration_seconds = float(
                    recorded_duration
                )

            runtime_state.clear_latest_sample()
            runtime_state.clear_alarm_state()

            vehicle = metadata.get("vehicle")

            if vehicle:
                runtime_state.update_vehicle_info(vehicle)

            alarm_engine = AlarmEngine.from_json_file(
                ALARM_RULES_PATH
            )

            previous_timestamp = None

            for index, sample_data in enumerate(samples):
                if (
                    self._stop_event is not None
                    and self._stop_event.is_set()
                ):
                    break

                self._wait_while_paused()

                if (
                    self._stop_event is not None
                    and self._stop_event.is_set()
                ):
                    break

                sample = sample_from_dict(sample_data)

                if previous_timestamp is not None:
                    delay_seconds = (
                        sample.timestamp - previous_timestamp
                    ).total_seconds()

                    delay_seconds = max(delay_seconds, 0.0)

                    with self._lock:
                        speed = self._speed

                    playback_delay = delay_seconds / speed

                    stop_event = self._stop_event

                    if (
                        playback_delay > 0
                        and stop_event is not None
                        and stop_event.wait(playback_delay)
                    ):
                        break

                alarm_events = alarm_engine.evaluate(sample)

                for event in alarm_events:
                    runtime_state.update_alarm_event(event)

                runtime_state.update_latest_sample(sample)

                elapsed_seconds = max(
                    0.0,
                    (
                        sample.timestamp
                        - first_sample.timestamp
                    ).total_seconds(),
                )

                with self._lock:
                    self._current_index = index + 1
                    self._elapsed_seconds = min(
                        elapsed_seconds,
                        self._duration_seconds,
                    )

                previous_timestamp = sample.timestamp

        except Exception as error:  # noqa: BLE001
            print("Playback error:", error)

            with self._lock:
                self._last_error = str(error)

        finally:
            with self._lock:
                self._state = "idle"
                self._thread = None
                self._stop_event = None
                self._trip_id = None


playback_controller = PlaybackController()
