def normalize_rpm(response):
    if response.is_null():
        return None

    return round(response.value.magnitude)


def normalize_speed_mph(response):
    if response.is_null():
        return None

    return round(response.value.to("mph").magnitude, 1)


def normalize_percent(response):
    if response.is_null():
        return None

    return round(response.value.magnitude, 1)