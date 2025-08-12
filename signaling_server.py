import asyncio
import os

from dotenv import load_dotenv
from websockets.asyncio.server import ServerConnection, serve

from utils import data_to_str

load_dotenv()

HOST: str = os.environ["SIGNALING_HOST"]
PORT: int = int(os.environ["SIGNALING_PORT"])
print(f"Listening on {HOST}:{PORT}")

clients: dict[str, ServerConnection] = {}


async def handler(ws: ServerConnection) -> None:
    peer_id: str = data_to_str(await ws.recv())
    clients[peer_id] = ws
    try:
        async for msg in ws:
            msg = data_to_str(msg)
            target_id, payload = msg.split(" ", 1)
            if target_id in clients:
                if payload.startswith("PORT"):
                    parts = payload.split()
                    if len(parts) >= 2:
                        port = parts[1]
                        ip = None
                        if getattr(ws, "remote_address", None):
                            try:
                                ip = ws.remote_address[0]
                            except Exception:
                                ip = None
                        if ip is not None:
                            await clients[target_id].send(f"{peer_id} IPPORT {ip} {port}")
                            continue
                await clients[target_id].send(f"{peer_id} {payload}")
    except Exception:
        pass
    finally:
        clients.pop(peer_id, None)


async def main() -> None:
    async with serve(handler, HOST, PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
