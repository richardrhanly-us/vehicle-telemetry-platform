def normalize_rpm(response):
    if response.is_null():
        return None

    return round(response.value.magnitude)


def normalize_speed_mph(response):
    if response.is_null():
        return None

    return round(
        response.value.to("mph").magnitude,
        1,
    )


def normalize_percent(response):
    if response.is_null():
        return None

    return round(response.value.magnitude, 1)


def normalize_temperature_f(response):
    if response.is_null():
        return None

    return round(
        response.value.to("degF").magnitude,
        1,
    )


def normalize_mass_air_flow(response):
    if response.is_null():
        return None

    return round(
        response.value.to("gram / second").magnitude,
        2,
    )


def normalize_pressure_kpa(response):
    if response.is_null():
        return None

    return round(
        response.value.to("kilopascal").magnitude,
        1,
    )


def normalize_voltage(response):
    if response.is_null():
        return None

    return round(
        response.value.to("volt").magnitude,
        2,
    )
