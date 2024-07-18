"""
Benchmark for asyncio websocket server and client performance
transferring 1MB of data.

Author: Kumar Aditya
"""

# import pyperf
from time import perf_counter
import websockets.server
import websockets.client
import websockets.exceptions
import asyncio

CHUNK_SIZE = 1024**2
DATA = b"x" * CHUNK_SIZE

stop: asyncio.Event


async def handler(websocket) -> None:
    for _ in range(150):
        await websocket.recv()

    stop.set()


async def main() -> float:
    global stop
    # t0 = pyperf.perf_counter()
    t0 = perf_counter()
    stop = asyncio.Event()
    try:
        async with websockets.server.serve(handler, "", 8001):
            async with websockets.client.connect("ws://localhost:8001") as ws:
                await asyncio.gather(*[ws.send(DATA) for _ in range(150)])
            await stop.wait()
    except websockets.exceptions.ConnectionClosedOK:
        pass
    # return pyperf.perf_counter() - t0
    return perf_counter() - t0


if __name__ == "__main__":
    # runner = pyperf.Runner()
    # runner.metadata["description"] = "Benchmark asyncio websockets"
    # runner.bench_async_func("asyncio_websockets", main)
    asyncio.run(main())
