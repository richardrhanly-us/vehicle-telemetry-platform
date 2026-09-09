import json
import time

from fastapi.testclient import TestClient

import api.server as server
import telemetry.playback_controller as playback_controller_module
from telemetry.playback_controller import playback_controller


client = TestClient(server.app)


def write_json(path, data):
    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )


def write_jsonl(path, items):
    path.write_text(
        "".join(
            json.dumps(item) + "\n"
            for item in items
        ),
        encoding="utf-8",
    )


def make_sample(sequence, timestamp):
    return {
        "sequence": sequence,
        "timestamp": timestamp,
        "rpm": 1500,
        "speed_mph": 20.0,
        "throttle_pct": 10.0,
        "load_pct": 30.0,
        "coolant_temp_f": 190.0,
        "intake_temp_f": 90.0,
        "ambient_temp_f": 70.0,
        "oil_temp_f": 200.0,
        "catalyst_temp_b1s1_f": 500.0,
        "catalyst_temp_b1s2_f": 500.0,
        "maf_gps": 5.0,
        "manifold_pressure_kpa": 100.0,
        "module_voltage_v": 14.0,
        "sample_duration_ms": 50.0,
        "sample_rate_hz": 1.0,
        "missing_values": 0,
        "query_failures": 0,
        "connection_status": "OBD_CONNECTED",
    }


def write_trip(tmp_path, trip_id, vehicle):
    write_json(
        tmp_path / f"trip_{trip_id}_metadata.json",
        {
            "start_time": "2026-09-07T12:00:00+00:00",
            "duration_seconds": 4.0,
            "vehicle": vehicle,
        },
    )

    write_jsonl(
        tmp_path / f"trip_{trip_id}.jsonl",
        [
            make_sample(
                1,
                "2026-09-07T12:00:00+00:00",
            ),
            make_sample(
                2,
                "2026-09-07T12:00:02+00:00",
            ),
            make_sample(
                3,
                "2026-09-07T12:00:04+00:00",
            ),
        ],
    )


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True

        time.sleep(0.02)

    return predicate()


def test_playback_status_carries_recorded_vehicle_metadata(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        playback_controller_module,
        "TRIPS_DIR",
        tmp_path,
    )

    vehicle = {
        "year": 2017,
        "make": "TOYOTA",
        "model": "COROLLA iM",
    }

    trip_id = "2026-09-07_12-00-00"

    write_trip(tmp_path, trip_id, vehicle)

    started = playback_controller.start(
        trip_id,
        speed=1.0,
    )

    assert started

    try:
        assert wait_for(
            lambda: playback_controller.get_status()["vehicle"]
            is not None
        )

        status = playback_controller.get_status()

        assert status["active"] is True
        assert status["vehicle"] == vehicle

    finally:
        playback_controller.stop()

        assert wait_for(
            lambda: not playback_controller.is_active()
        )

    assert playback_controller.get_status()["vehicle"] is None


def test_vehicle_scan_is_blocked_while_playback_is_active(
    monkeypatch,
):
    monkeypatch.setattr(
        playback_controller,
        "is_active",
        lambda: True,
    )

    response = client.post(
        "/api/vehicle/scan?interactive=false"
    )

    assert response.status_code == 409
    assert "playback" in response.json()["detail"].lower()
