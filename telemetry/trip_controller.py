import threading
import time

import telemetry.runtime_state as runtime_state
from telemetry.collector import (
    check_vehicle_connection,
    run_collector,
    scan_for_vehicle,
)


PRESENCE_CHECK_INTERVAL_SECONDS = 3


class TripController:
    def __init__(self):
        self._lock = threading.Lock()

        self._thread = None
        self._stop_event = None

        self._scan_thread = None
        self._presence_thread = None
        self._presence_stop_event = (
            threading.Event()
        )

        self._state = "idle"
        self._last_error = None

        self._vehicle = None
        self._vehicle_state = "waiting"
        self._vehicle_error = None

        self._presence_thread = (
            threading.Thread(
                target=self._presence_monitor,
                daemon=True,
            )
        )

        self._presence_thread.start()

    def is_recording(self):
        with self._lock:
            return (
                self._state == "recording"
            )

    def get_status(self):
        with self._lock:
            return {
                "state": self._state,
                "recording":
                    self._state
                    == "recording",
                "error":
                    self._last_error,
                "vehicle_ready":
                    self._vehicle
                    is not None,
                "active_alarms":
                    runtime_state
                    .get_active_alarms(),
                "latest_alarm_event":
                    runtime_state
                    .latest_alarm_event,
            }

    def get_vehicle_status(self):
        with self._lock:
            return {
                "state":
                    self._vehicle_state,
                "ready":
                    self._vehicle
                    is not None,
                "scanning":
                    self._vehicle_state
                    == "scanning",
                "error":
                    self._vehicle_error,
                "vehicle":
                    runtime_state
                    .vehicle_info,
            }

    def scan_vehicle(
        self,
        interactive=False,
    ):
        with self._lock:
            if (
                self._state != "idle"
            ):
                return False

            if (
                self._scan_thread
                is not None
                and self._scan_thread
                .is_alive()
            ):
                return False

            self._vehicle = None

            self._vehicle_state = (
                "scanning"
            )

            self._vehicle_error = None

            runtime_state.clear_vehicle_info()

            self._scan_thread = (
                threading.Thread(
                    target=
                        self._run_vehicle_scan,
                    args=(interactive,),
                    daemon=True,
                )
            )

            self._scan_thread.start()

            return True

    def start_trip(self):
        with self._lock:
            if (
                self._state != "idle"
            ):
                return False

            if self._vehicle is None:
                return False

            if (
                self._scan_thread
                is not None
                and self._scan_thread
                .is_alive()
            ):
                return False

            runtime_state.clear_latest_sample()
            runtime_state.clear_alarm_state()

            vehicle = self._vehicle

            self._stop_event = (
                threading.Event()
            )

            self._state = "recording"
            self._last_error = None

            self._thread = (
                threading.Thread(
                    target=self._run_trip,
                    args=(vehicle,),
                    daemon=True,
                )
            )

            self._thread.start()

            return True

    def stop_trip(self):
        with self._lock:
            if (
                self._state
                != "recording"
            ):
                return False

            if (
                self._stop_event
                is not None
            ):
                self._stop_event.set()

            self._state = "stopping"

            return True

    def _run_vehicle_scan(
        self,
        interactive,
    ):
        try:
            vehicle = scan_for_vehicle(
                allow_profile_prompt=
                    interactive,
            )

            with self._lock:
                if vehicle is None:
                    self._vehicle = None

                    self._vehicle_state = (
                        "waiting"
                    )

                    runtime_state.clear_vehicle_info()

                else:
                    self._vehicle = vehicle

                    self._vehicle_state = (
                        "ready"
                    )

                    runtime_state.update_vehicle_info(
                        vehicle
                    )

        except Exception as error:
            print(
                "Vehicle scan error:",
                error,
            )

            with self._lock:
                self._vehicle = None

                self._vehicle_state = (
                    "error"
                )

                self._vehicle_error = (
                    str(error)
                )

                runtime_state.clear_vehicle_info()

        finally:
            with self._lock:
                self._scan_thread = None

    def _presence_monitor(self):
        while not (
            self._presence_stop_event
            .is_set()
        ):
            self._presence_stop_event.wait(
                PRESENCE_CHECK_INTERVAL_SECONDS
            )

            if (
                self._presence_stop_event
                .is_set()
            ):
                break

            with self._lock:
                should_check = (
                    self._state == "idle"
                    and self._vehicle
                    is not None
                    and (
                        self._scan_thread
                        is None
                        or not self._scan_thread
                        .is_alive()
                    )
                )

            if not should_check:
                continue

            connected = (
                check_vehicle_connection()
            )

            if connected:
                continue

            print(
                "Vehicle connection lost."
            )

            with self._lock:
                self._vehicle = None

                self._vehicle_state = (
                    "waiting"
                )

                self._vehicle_error = None

                runtime_state.clear_vehicle_info()
                runtime_state.clear_latest_sample()
                runtime_state.clear_alarm_state()

    def _run_trip(
        self,
        vehicle,
    ):
        try:
            run_collector(
                stop_event=
                    self._stop_event,
                vehicle=vehicle,
                on_sample=
                    runtime_state
                    .update_latest_sample,
                on_alarm=
                    runtime_state
                    .update_alarm_event,
            )

        except Exception as error:
            print(
                "Trip collector error:",
                error,
            )

            with self._lock:
                self._last_error = (
                    str(error)
                )

                self._vehicle = None

                self._vehicle_state = (
                    "waiting"
                )

                runtime_state.clear_vehicle_info()
                runtime_state.clear_latest_sample()
                runtime_state.clear_alarm_state()

        finally:
            with self._lock:
                self._state = "idle"
                self._thread = None
                self._stop_event = None


trip_controller = TripController()
