latest_sample = None
vehicle_info = None


def update_latest_sample(sample):
    global latest_sample

    latest_sample = sample.to_dict()


def update_vehicle_info(vehicle):
    global vehicle_info

    vehicle_info = {
        "year": vehicle.year,
        "make": vehicle.make,
        "model": vehicle.model,
    }


def clear_latest_sample():
    global latest_sample

    latest_sample = None


def clear_vehicle_info():
    global vehicle_info

    vehicle_info = None


def clear_live_state():
    clear_latest_sample()
    clear_vehicle_info()
