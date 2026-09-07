import asyncio

import websockets


async def main():
    uri = "ws://127.0.0.1:8000/ws/telemetry"

    async with websockets.connect(uri) as websocket:
        print("Connected to telemetry stream.")

        while True:
            message = await websocket.recv()
            print(message)


asyncio.run(main())