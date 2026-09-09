import obd

connection = obd.OBD("COM3")

for command in connection.supported_commands:
    name = str(command.name).upper()

    if (
        "GEAR" in name
        or "TRANS" in name
        or "NEUT" in name
        or "DRIVE" in name
    ):
        print(command.name)

connection.close()