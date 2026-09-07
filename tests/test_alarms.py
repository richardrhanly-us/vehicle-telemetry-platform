from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from telemetry.alarms import AlarmEngine, AlarmRule


def make_sample(
    sequence,
    timestamp,
    rpm=None,
    load_pct=None,
):
    return SimpleNamespace(
        sequence=sequence,
        timestamp=timestamp,
        rpm=rpm,
        load_pct=load_pct,
    )


def make_engine(
    *,
    threshold=1500,
    duration_seconds=2,
):
    rule = AlarmRule(
        name="High RPM",
        field="rpm",
        operator=">",
        threshold=threshold,
        duration_seconds=duration_seconds,
        severity="warning",
    )

    return AlarmEngine([rule])


def test_alarm_does_not_trigger_before_duration():
    engine = make_engine()
    start = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    first_events = engine.evaluate(
        make_sample(
            1,
            start,
            rpm=1800,
        )
    )

    second_events = engine.evaluate(
        make_sample(
            2,
            start + timedelta(seconds=1),
            rpm=1800,
        )
    )

    assert first_events == []
    assert second_events == []
    assert engine.active_alarms() == []


def test_alarm_triggers_after_required_duration():
    engine = make_engine()
    start = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    engine.evaluate(
        make_sample(
            1,
            start,
            rpm=1800,
        )
    )

    events = engine.evaluate(
        make_sample(
            2,
            start + timedelta(seconds=2),
            rpm=1800,
        )
    )

    assert len(events) == 1

    event = events[0]

    assert event["type"] == "triggered"
    assert event["rule"] == "High RPM"
    assert event["severity"] == "warning"
    assert event["field"] == "rpm"
    assert event["operator"] == ">"
    assert event["threshold"] == 1500
    assert event["value"] == 1800
    assert event["sequence"] == 2
    assert event["duration_seconds"] == 2.0
    assert engine.active_alarms() == ["High RPM"]


def test_alarm_does_not_repeat_trigger_while_still_active():
    engine = make_engine()
    start = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    engine.evaluate(
        make_sample(
            1,
            start,
            rpm=1800,
        )
    )

    engine.evaluate(
        make_sample(
            2,
            start + timedelta(seconds=2),
            rpm=1800,
        )
    )

    events = engine.evaluate(
        make_sample(
            3,
            start + timedelta(seconds=3),
            rpm=2000,
        )
    )

    assert events == []
    assert engine.active_alarms() == ["High RPM"]


def test_alarm_clears_when_condition_returns_to_normal():
    engine = make_engine()
    start = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    engine.evaluate(
        make_sample(
            1,
            start,
            rpm=1800,
        )
    )

    engine.evaluate(
        make_sample(
            2,
            start + timedelta(seconds=2),
            rpm=1800,
        )
    )

    events = engine.evaluate(
        make_sample(
            3,
            start + timedelta(seconds=5),
            rpm=900,
        )
    )

    assert len(events) == 1

    event = events[0]

    assert event["type"] == "cleared"
    assert event["rule"] == "High RPM"
    assert event["value"] == 900
    assert event["reason"] == "condition_cleared"
    assert event["duration_seconds"] == 5.0
    assert engine.active_alarms() == []


def test_missing_value_clears_triggered_alarm():
    engine = make_engine()
    start = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    engine.evaluate(
        make_sample(
            1,
            start,
            rpm=1800,
        )
    )

    engine.evaluate(
        make_sample(
            2,
            start + timedelta(seconds=2),
            rpm=1800,
        )
    )

    events = engine.evaluate(
        make_sample(
            3,
            start + timedelta(seconds=3),
            rpm=None,
        )
    )

    assert len(events) == 1
    assert events[0]["type"] == "cleared"
    assert events[0]["reason"] == "value_missing"
    assert events[0]["value"] is None


def test_reset_clears_alarm_state():
    engine = make_engine()
    start = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    engine.evaluate(
        make_sample(
            1,
            start,
            rpm=1800,
        )
    )

    engine.evaluate(
        make_sample(
            2,
            start + timedelta(seconds=2),
            rpm=1800,
        )
    )

    assert engine.active_alarms() == ["High RPM"]

    engine.reset()

    assert engine.active_alarms() == []


def test_invalid_operator_in_config_raises_value_error(
    tmp_path,
):
    config_file = tmp_path / "alarm_rules.json"

    config_file.write_text(
        """
        {
          "rules": [
            {
              "name": "Bad Rule",
              "field": "rpm",
              "operator": "approximately",
              "threshold": 1000,
              "duration_seconds": 1,
              "severity": "warning"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported alarm operator",
    ):
        AlarmEngine.from_json_file(
            config_file
        )
