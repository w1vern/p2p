
import asyncio
import os
import socket
from typing import Optional, Tuple

import aiohttp
from dotenv import load_dotenv
from websockets.asyncio.client import connect

from utils import data_to_str

load_dotenv()

SIGNALING_HOST: str = os.environ["SIGNALING_HOST"]
SIGNALING_PORT: str = os.environ["SIGNALING_PORT"]
SIGNALING_SERVER = f"ws://{SIGNALING_HOST}:{SIGNALING_PORT}"
LOCAL_SERVER_HOST: str = os.environ["LOCAL_SERVER_HOST"]
LOCAL_SERVER_PORT: int = int(os.environ["LOCAL_SERVER_PORT"])
LOCAL_TARGET = f"http://{LOCAL_SERVER_HOST}:{LOCAL_SERVER_PORT}"

udp_sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind(("", 0))
udp_sock.setblocking(False)

peer_addr: Optional[Tuple[str, int]] = None


async def signaling() -> None:
    global peer_addr
    async with connect(SIGNALING_SERVER) as ws:
        await ws.send("SERVER")
        local_port: int = udp_sock.getsockname()[1]
        await ws.send(f"CLIENT PORT {local_port}")
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
            elif payload.startswith("GET"):
                path = payload.split(" ", 1)[1]
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(LOCAL_TARGET.rstrip("/") + path) as resp:
                        body: bytes = await resp.read()
                await ws.send(body)


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


async def udp_listener() -> None:
    global peer_addr
    loop = asyncio.get_running_loop()
    while True:
        try:
            data, addr = await loop.sock_recvfrom(udp_sock, 65535)
            if data == b"ping":
                peer_addr = addr
                await loop.sock_sendto(udp_sock, b"pong", addr)
            elif data.startswith(b"GET"):
                try:
                    path = data.decode(errors="ignore").split(" ", 1)[1]
                except Exception:
                    path = "/"
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(LOCAL_TARGET.rstrip("/") + path) as resp:
                        body: bytes = await resp.read()
                await loop.sock_sendto(udp_sock, body, addr)
        except BlockingIOError:
            await asyncio.sleep(0.01)
        except Exception:
            await asyncio.sleep(0.01)


async def main() -> None:
    await asyncio.gather(signaling(), udp_listener())

if __name__ == "__main__":
    asyncio.run(main())
