import obd

connection = obd.OBD("COM3")

for command in connection.supported_commands:
    name = str(command.name).upper()

    if (
        "TEMP" in name
        or "AMBI" in name
        or "AIR" in name
    ):
        print(command.name)

connection.close()