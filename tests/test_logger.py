import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from telemetry.logger import (
    log_alarm_event,
    write_trip_metadata,
)


def test_log_alarm_event_writes_jsonl(tmp_path):
    events_file = tmp_path / "events.jsonl"

    event = {
        "type": "triggered",
        "rule": "High RPM",
        "sequence": 7,
        "value": 1882,
    }

    log_alarm_event(
        events_file,
        event,
    )

    lines = events_file.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0]) == event


def test_multiple_alarm_events_are_appended(tmp_path):
    events_file = tmp_path / "events.jsonl"

    triggered = {
        "type": "triggered",
        "rule": "High RPM",
        "sequence": 7,
    }

    cleared = {
        "type": "cleared",
        "rule": "High RPM",
        "sequence": 23,
    }

    log_alarm_event(
        events_file,
        triggered,
    )

    log_alarm_event(
        events_file,
        cleared,
    )

    events = [
        json.loads(line)
        for line in events_file.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert events == [
        triggered,
        cleared,
    ]


def test_trip_metadata_contains_alarm_counts(tmp_path):
    metadata_file = (
        tmp_path / "trip_metadata.json"
    )

    start_time = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    end_time = (
        start_time
        + timedelta(seconds=30)
    )

    vehicle = SimpleNamespace(
        year=2017,
        make="TOYOTA",
        model="COROLLA iM",
    )

    write_trip_metadata(
        metadata_file,
        start_time,
        end_time,
        10,
        3000,
        25.0,
        15000,
        100.0,
        700.0,
        9.0,
        9,
        0,
        0,
        vehicle,
        0.1,
        20.0,
        10.0,
        2,
        1,
        1,
    )

    metadata = json.loads(
        metadata_file.read_text(
            encoding="utf-8"
        )
    )

    assert metadata[
        "alarm_event_count"
    ] == 2

    assert metadata[
        "alarm_trigger_count"
    ] == 1

    assert metadata[
        "alarm_clear_count"
    ] == 1

    assert metadata["vehicle"] == {
        "year": 2017,
        "make": "TOYOTA",
        "model": "COROLLA iM",
    }
