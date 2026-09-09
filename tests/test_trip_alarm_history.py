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


def make_metadata(vehicle=None):
    return {
        "start_time": "2026-09-07T12:00:00+00:00",
        "end_time": "2026-09-07T12:01:00+00:00",
        "duration_seconds": 60.0,
        "sample_count": 3,
        "distance_miles": 0.5,
        "vehicle": vehicle
        or {
            "year": 2017,
            "make": "TOYOTA",
            "model": "COROLLA iM",
        },
        "alarm_event_count": 2,
        "alarm_trigger_count": 1,
        "alarm_clear_count": 1,
    }


def make_sample(sequence, timestamp, load_pct):
    return {
        "sequence": sequence,
        "timestamp": timestamp,
        "load_pct": load_pct,
    }


def make_high_load_events():
    return [
        {
            "type": "triggered",
            "timestamp": "2026-09-07T12:00:07+00:00",
            "sequence": 7,
            "rule": "High Engine Load",
            "severity": "warning",
            "field": "load_pct",
            "operator": ">",
            "threshold": 10.0,
            "value": 87.2,
            "duration_seconds": 3.0,
            "duration_requirement_seconds": 3,
        },
        {
            "type": "cleared",
            "timestamp": "2026-09-07T12:00:10+00:00",
            "sequence": 10,
            "rule": "High Engine Load",
            "severity": "warning",
            "field": "load_pct",
            "operator": ">",
            "threshold": 10.0,
            "value": 4.1,
            "duration_seconds": 3.2,
            "duration_requirement_seconds": 3,
            "reason": "condition_cleared",
        },
    ]


def write_trip_with_events(tmp_path, trip_id, events):
    write_json(
        tmp_path / f"trip_{trip_id}_metadata.json",
        make_metadata(),
    )

    write_jsonl(
        tmp_path / f"trip_{trip_id}.jsonl",
        [
            make_sample(7, "2026-09-07T12:00:07+00:00", 87.2),
            make_sample(8, "2026-09-07T12:00:08+00:00", 60.0),
            make_sample(9, "2026-09-07T12:00:09+00:00", 30.0),
            make_sample(10, "2026-09-07T12:00:10+00:00", 4.1),
        ],
    )

    if events:
        write_jsonl(
            tmp_path / f"trip_{trip_id}_events.jsonl",
            events,
        )


def test_recorded_trip_exposes_alarm_events_through_the_api(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(server, "TRIPS_DIR", tmp_path)

    trip_id = "2026-09-07_12-00-00"
    events = make_high_load_events()

    write_trip_with_events(tmp_path, trip_id, events)

    response = client.get(f"/api/trips/{trip_id}")

    assert response.status_code == 200

    body = response.json()

    assert body["events"] == events


def test_alarm_event_metadata_survives_persistence_round_trip(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(server, "TRIPS_DIR", tmp_path)

    trip_id = "2026-09-07_12-00-00"
    events = make_high_load_events()

    write_trip_with_events(tmp_path, trip_id, events)

    response = client.get(f"/api/trips/{trip_id}")
    event = response.json()["events"][0]

    assert event["rule"] == "High Engine Load"
    assert event["severity"] == "warning"
    assert event["field"] == "load_pct"
    assert event["operator"] == ">"
    assert event["threshold"] == 10.0
    assert event["value"] == 87.2
    assert event["sequence"] == 7
    assert event["duration_requirement_seconds"] == 3


def test_alarm_event_sequence_maps_to_a_recorded_sample(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(server, "TRIPS_DIR", tmp_path)

    trip_id = "2026-09-07_12-00-00"
    events = make_high_load_events()

    write_trip_with_events(tmp_path, trip_id, events)

    response = client.get(f"/api/trips/{trip_id}")
    body = response.json()

    sample_sequences = {
        sample["sequence"] for sample in body["samples"]
    }

    for event in body["events"]:
        assert event["sequence"] in sample_sequences


def test_trip_without_events_file_still_loads_with_empty_events(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(server, "TRIPS_DIR", tmp_path)

    trip_id = "2026-09-07_13-00-00"

    write_trip_with_events(tmp_path, trip_id, events=None)

    response = client.get(f"/api/trips/{trip_id}")

    assert response.status_code == 200
    assert response.json()["events"] == []


def make_full_sample(sequence, timestamp, load_pct):
    return {
        "sequence": sequence,
        "timestamp": timestamp,
        "rpm": 1500,
        "speed_mph": 20.0,
        "throttle_pct": 10.0,
        "load_pct": load_pct,
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


def write_full_trip_with_events(tmp_path, trip_id, events):
    write_json(
        tmp_path / f"trip_{trip_id}_metadata.json",
        make_metadata(),
    )

    write_jsonl(
        tmp_path / f"trip_{trip_id}.jsonl",
        [
            make_full_sample(
                7, "2026-09-07T12:00:07+00:00", 87.2
            ),
            make_full_sample(
                8, "2026-09-07T12:00:08+00:00", 60.0
            ),
            make_full_sample(
                9, "2026-09-07T12:00:09+00:00", 30.0
            ),
            make_full_sample(
                10, "2026-09-07T12:00:10+00:00", 4.1
            ),
        ],
    )

    write_jsonl(
        tmp_path / f"trip_{trip_id}_events.jsonl",
        events,
    )


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True

        time.sleep(0.02)

    return predicate()


def test_playback_does_not_modify_original_recorded_alarm_history(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        playback_controller_module,
        "TRIPS_DIR",
        tmp_path,
    )

    trip_id = "2026-09-07_12-00-00"
    events = make_high_load_events()

    write_full_trip_with_events(tmp_path, trip_id, events)

    events_file = tmp_path / f"trip_{trip_id}_events.jsonl"
    original_contents = events_file.read_text(encoding="utf-8")

    started = playback_controller.start(trip_id, speed=10.0)
    assert started

    try:
        assert wait_for(
            lambda: not playback_controller.is_active(),
            timeout=5.0,
        )
    finally:
        playback_controller.stop()

    assert events_file.read_text(encoding="utf-8") == (
        original_contents
    )
