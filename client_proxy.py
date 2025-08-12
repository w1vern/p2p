
import asyncio
import os
import socket
from typing import Optional, Tuple

from aiohttp import web
from dotenv import load_dotenv
from websockets.asyncio.client import connect

from utils import data_to_str

load_dotenv()

SIGNALING_HOST: str = os.environ["SIGNALING_HOST"]
SIGNALING_PORT: str = os.environ["SIGNALING_PORT"]
SIGNALING_SERVER = f"ws://{SIGNALING_HOST}:{SIGNALING_PORT}"
print(SIGNALING_SERVER)
LOCAL_REMOTE_HOST: str = os.environ["LOCAL_REMOTE_HOST"]
LOCAL_REMOTE_PORT: int = int(os.environ["LOCAL_REMOTE_PORT"])
LOCAL_TARGET = f"{LOCAL_REMOTE_HOST}:{LOCAL_REMOTE_PORT}"
print(LOCAL_TARGET)
udp_sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind(("", 0))
udp_sock.setblocking(False)

peer_addr: Optional[Tuple[str, int]] = None


async def signaling() -> None:
    global peer_addr
    async with connect(SIGNALING_SERVER) as ws:
        await ws.send("CLIENT")
        local_port: int = udp_sock.getsockname()[1]
        await ws.send(f"SERVER PORT {local_port}")
        async for msg in ws:
            msg = data_to_str(msg)
            try:
                sender, payload = msg.split(" ", 1)
            except ValueError:
                continue
            if payload.startswith("IPPORT"):
                parts = payload.split()
                if len(parts) >= 3:
                    ip = parts[1]
                    port = int(parts[2])
                    peer_addr = (ip, port)
                    asyncio.create_task(punch_peer())


async def punch_peer() -> None:
    global peer_addr
    if peer_addr is None:
        return
    loop = asyncio.get_running_loop()
    for _ in range(6):
        try:
            await loop.sock_sendto(udp_sock, b"ping", peer_addr)
        except Exception:
            pass
        await asyncio.sleep(0.2)


async def fetch_from_server(path: str):
    if peer_addr is None:
        return web.Response(status=503, text="Peer not connected")
    loop = asyncio.get_running_loop()
    await loop.sock_sendto(udp_sock, f"GET {path}".encode(), peer_addr)
    data, _ = await loop.sock_recvfrom(udp_sock, 65535)
    return web.Response(body=data)


async def start_http_proxy() -> None:
    app = web.Application()

    async def handler(request):
        tail = request.match_info.get("tail", "")
        path = "/" + tail if tail else "/"
        return await fetch_from_server(path)
    app.router.add_route("GET", "/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, LOCAL_REMOTE_HOST, LOCAL_REMOTE_PORT)
    await site.start()


async def main() -> None:
    await asyncio.gather(signaling(), start_http_proxy())

if __name__ == "__main__":
    asyncio.run(main())
