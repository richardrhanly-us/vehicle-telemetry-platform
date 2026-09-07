import json

from fastapi.testclient import TestClient

import api.server as server


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


def make_metadata(
    *,
    start_time="2026-09-07T12:00:00+00:00",
    alarm_event_count=2,
    alarm_trigger_count=1,
    alarm_clear_count=1,
):
    return {
        "start_time": start_time,
        "end_time": "2026-09-07T12:01:00+00:00",
        "duration_seconds": 60.0,
        "sample_count": 2,
        "distance_miles": 0.5,
        "vehicle": {
            "year": 2017,
            "make": "TOYOTA",
            "model": "COROLLA iM",
        },
        "max_rpm": 2200,
        "max_speed_mph": 20.0,
        "average_rpm": 1500,
        "average_speed_mph": 10.0,
        "average_sample_duration_ms": 70.0,
        "average_sample_rate_hz": 0.9,
        "total_missing_values": 0,
        "total_query_failures": 0,
        "moving_time_seconds": 30.0,
        "stopped_time_seconds": 30.0,
        "average_moving_speed_mph": 12.0,
        "alarm_event_count": alarm_event_count,
        "alarm_trigger_count": alarm_trigger_count,
        "alarm_clear_count": alarm_clear_count,
    }


def test_trip_list_returns_summaries_sorted_newest_first(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    older_id = "2026-09-07_12-00-00"
    newer_id = "2026-09-07_13-00-00"

    write_json(
        tmp_path
        / f"trip_{older_id}_metadata.json",
        make_metadata(
            start_time="2026-09-07T12:00:00+00:00"
        ),
    )

    write_json(
        tmp_path
        / f"trip_{newer_id}_metadata.json",
        make_metadata(
            start_time="2026-09-07T13:00:00+00:00"
        ),
    )

    response = client.get("/api/trips")

    assert response.status_code == 200

    trips = response.json()

    assert [
        trip["trip_id"]
        for trip in trips
    ] == [
        newer_id,
        older_id,
    ]

    assert trips[0]["vehicle"] == {
        "year": 2017,
        "make": "TOYOTA",
        "model": "COROLLA iM",
    }


def test_trip_detail_returns_metadata_samples_and_events(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    trip_id = "2026-09-07_12-00-00"

    write_json(
        tmp_path
        / f"trip_{trip_id}_metadata.json",
        make_metadata(),
    )

    samples = [
        {
            "sequence": 1,
            "rpm": 900,
            "speed_mph": 0.0,
        },
        {
            "sequence": 2,
            "rpm": 1800,
            "speed_mph": 5.0,
        },
    ]

    events = [
        {
            "type": "triggered",
            "rule": "High RPM",
            "sequence": 2,
        },
        {
            "type": "cleared",
            "rule": "High RPM",
            "sequence": 3,
        },
    ]

    write_jsonl(
        tmp_path / f"trip_{trip_id}.jsonl",
        samples,
    )

    write_jsonl(
        tmp_path
        / f"trip_{trip_id}_events.jsonl",
        events,
    )

    response = client.get(
        f"/api/trips/{trip_id}"
    )

    assert response.status_code == 200

    trip = response.json()

    assert trip["trip_id"] == trip_id
    assert trip["samples"] == samples
    assert trip["events"] == events
    assert trip["metadata"]["alarm_event_count"] == 2
    assert trip["metadata"]["alarm_trigger_count"] == 1
    assert trip["metadata"]["alarm_clear_count"] == 1


def test_old_trip_without_event_file_loads_with_empty_events(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    trip_id = "2026-08-01_10-00-00"

    metadata = make_metadata(
        alarm_event_count=0,
        alarm_trigger_count=0,
        alarm_clear_count=0,
    )

    metadata.pop(
        "alarm_event_count"
    )
    metadata.pop(
        "alarm_trigger_count"
    )
    metadata.pop(
        "alarm_clear_count"
    )

    write_json(
        tmp_path
        / f"trip_{trip_id}_metadata.json",
        metadata,
    )

    write_jsonl(
        tmp_path / f"trip_{trip_id}.jsonl",
        [{"sequence": 1, "rpm": 800}],
    )

    response = client.get(
        f"/api/trips/{trip_id}"
    )

    assert response.status_code == 200

    trip = response.json()

    assert trip["events"] == []
    assert trip["metadata"]["alarm_event_count"] == 0
    assert trip["metadata"]["alarm_trigger_count"] == 0
    assert trip["metadata"]["alarm_clear_count"] == 0


def test_missing_trip_returns_404(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    response = client.get(
        "/api/trips/does-not-exist"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Trip not found."
    }


def test_invalid_trip_id_is_rejected(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    response = client.get(
        "/api/trips/..%5Csecret"
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid trip ID."
    }


def test_malformed_metadata_returns_500_instead_of_crashing(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    trip_id = "2026-09-07_14-00-00"

    metadata_file = (
        tmp_path
        / f"trip_{trip_id}_metadata.json"
    )

    metadata_file.write_text(
        "{this is not valid json",
        encoding="utf-8",
    )

    response = client.get(
        f"/api/trips/{trip_id}"
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail":
            "Trip metadata could not be read."
    }


def test_malformed_jsonl_lines_are_skipped(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    trip_id = "2026-09-07_15-00-00"

    write_json(
        tmp_path
        / f"trip_{trip_id}_metadata.json",
        make_metadata(),
    )

    trip_file = (
        tmp_path
        / f"trip_{trip_id}.jsonl"
    )

    trip_file.write_text(
        '{"sequence": 1, "rpm": 900}\n'
        'not valid json\n'
        '{"sequence": 2, "rpm": 1000}\n',
        encoding="utf-8",
    )

    response = client.get(
        f"/api/trips/{trip_id}"
    )

    assert response.status_code == 200

    samples = response.json()["samples"]

    assert samples == [
        {
            "sequence": 1,
            "rpm": 900,
        },
        {
            "sequence": 2,
            "rpm": 1000,
        },
    ]


def test_trip_list_skips_malformed_metadata_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        server,
        "TRIPS_DIR",
        tmp_path,
    )

    good_id = "2026-09-07_16-00-00"
    bad_id = "2026-09-07_17-00-00"

    write_json(
        tmp_path
        / f"trip_{good_id}_metadata.json",
        make_metadata(),
    )

    (
        tmp_path
        / f"trip_{bad_id}_metadata.json"
    ).write_text(
        "broken",
        encoding="utf-8",
    )

    response = client.get("/api/trips")

    assert response.status_code == 200

    trips = response.json()

    assert len(trips) == 1
    assert trips[0]["trip_id"] == good_id
