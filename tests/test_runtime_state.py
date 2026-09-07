from types import SimpleNamespace

import telemetry.runtime_state as runtime_state


def setup_function():
    runtime_state.clear_live_state()


def test_triggered_alarm_becomes_active():
    event = {
        "type": "triggered",
        "rule": "High RPM",
        "severity": "warning",
        "value": 1800,
    }

    runtime_state.update_alarm_event(
        event
    )

    assert (
        runtime_state.latest_alarm_event
        == event
    )

    assert runtime_state.get_active_alarms() == [
        event
    ]


def test_cleared_alarm_is_removed_from_active_alarms():
    triggered = {
        "type": "triggered",
        "rule": "High RPM",
        "value": 1800,
    }

    cleared = {
        "type": "cleared",
        "rule": "High RPM",
        "value": 900,
    }

    runtime_state.update_alarm_event(
        triggered
    )

    runtime_state.update_alarm_event(
        cleared
    )

    assert runtime_state.get_active_alarms() == []

    assert (
        runtime_state.latest_alarm_event
        == cleared
    )


def test_clear_alarm_state_resets_live_alarm_data():
    runtime_state.update_alarm_event(
        {
            "type": "triggered",
            "rule": "High RPM",
        }
    )

    runtime_state.clear_alarm_state()

    assert runtime_state.get_active_alarms() == []
    assert runtime_state.latest_alarm_event is None


def test_clear_live_state_resets_sample_vehicle_and_alarm():
    runtime_state.latest_sample = {
        "sequence": 1
    }

    runtime_state.vehicle_info = {
        "year": 2017
    }

    runtime_state.update_alarm_event(
        {
            "type": "triggered",
            "rule": "High RPM",
        }
    )

    runtime_state.clear_live_state()

    assert runtime_state.latest_sample is None
    assert runtime_state.vehicle_info is None
    assert runtime_state.get_active_alarms() == []
    assert runtime_state.latest_alarm_event is None
