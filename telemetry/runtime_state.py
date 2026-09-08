latest_sample = None
latest_sample_revision = 0

vehicle_info = None

active_alarms = {}
latest_alarm_event = None


def update_latest_sample(sample):
    global latest_sample
    global latest_sample_revision

    if isinstance(sample, dict):
        latest_sample = dict(sample)
    else:
        latest_sample = sample.to_dict()

    latest_sample_revision += 1


def update_vehicle_info(vehicle):
    global vehicle_info

    if isinstance(vehicle, dict):
        vehicle_info = {
            "year": vehicle.get("year"),
            "make": vehicle.get("make"),
            "model": vehicle.get("model"),
        }
        return

    vehicle_info = {
        "year": vehicle.year,
        "make": vehicle.make,
        "model": vehicle.model,
    }


def update_alarm_event(event):
    global latest_alarm_event

    latest_alarm_event = event

    rule_name = event.get("rule")
    event_type = event.get("type")

    if not rule_name:
        return

    if event_type == "triggered":
        active_alarms[rule_name] = event
    elif event_type == "cleared":
        active_alarms.pop(rule_name, None)


def get_active_alarms():
    return list(active_alarms.values())


def clear_latest_sample():
    global latest_sample
    global latest_sample_revision

    latest_sample = None
    latest_sample_revision += 1


def clear_vehicle_info():
    global vehicle_info
    vehicle_info = None


def clear_alarm_state():
    global latest_alarm_event

    active_alarms.clear()
    latest_alarm_event = None


def clear_live_state():
    clear_latest_sample()
    clear_vehicle_info()
    clear_alarm_state()
