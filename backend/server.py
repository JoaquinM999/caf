import asyncio
import json
import logging
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from caf.engine import CafEngine
from caf.profiles_manager import get_available_profiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("server")

app = FastAPI(title="Caf V2 Backend")

engine = None
engine_task = None
# Cola de eventos del servidor: sobrevive a los cambios de perfil.
events = asyncio.Queue()
_lock = asyncio.Lock()


def _on_done(t: asyncio.Task):
    if t.cancelled():
        return
    exc = t.exception()
    if exc:
        logger.error(f"ENGINE CRASHED: {exc!r}")
        events.put_nowait({"estado": "error", "detalle": str(exc)})


async def start_engine(profile_name: str):
    """(Re)inicia el motor con un perfil. Detiene el anterior primero."""
    global engine, engine_task
    async with _lock:
        if engine is not None:
            engine.stop()
            if engine_task:
                engine_task.cancel()
                await asyncio.gather(engine_task, return_exceptions=True)
        engine = CafEngine(profile_name=profile_name, use_audio_hardware=True, events_queue=events)
        engine_task = asyncio.create_task(engine.start())
        engine_task.add_done_callback(_on_done)


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Caf V2 Backend is running."}


@app.get("/profiles")
def get_profiles():
    return {"profiles": get_available_profiles()}


@app.post("/profiles/change")
async def change_profile(profile_name: str):
    await start_engine(profile_name)
    return {"status": "ok", "message": f"Profile changed to {profile_name}"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected.")

    if engine is None or not engine.is_running:
        try:
            await start_engine("amiguito")
        except Exception as e:
            logger.error(f"No se pudo iniciar el motor: {e!r}")
            await websocket.send_text(json.dumps({"estado": "error", "detalle": str(e)}))

    async def receive_from_ws():
        try:
            while True:
                data = await websocket.receive()
                if data.get("type") == "websocket.disconnect":
                    return
                if data.get("text") is None:
                    continue
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    logger.warning(f"JSON invalido: {data['text']!r}")
                    continue
                action = msg.get("action")
                if action == "hablar" and msg.get("text") and engine:
                    engine.text_in_queue.put_nowait(msg["text"])
                elif action == "cambiar_perfil" and msg.get("perfil"):
                    await start_engine(msg["perfil"])
                elif action == "ptt" and engine:  # {"action":"ptt","down":true|false}
                    engine.ptt_enabled = True
                    engine.set_ptt(bool(msg.get("down")))
                elif action == "despertar" and engine:
                    engine.request_wake()
                elif action == "dormir" and engine:
                    engine.request_sleep()
                elif action in ("silenciar", "activar") and engine:
                    engine.muted = action == "silenciar"
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected.")
        except Exception as e:
            logger.error(f"WS receive error: {e!r}")

    async def send_to_ws():
        # El audio NO se manda por aca: lo reproduce el motor en los parlantes locales.
        try:
            while True:
                event = await events.get()
                await websocket.send_text(json.dumps(event))
        except Exception as e:
            logger.error(f"WS send error: {e!r}")

    recv_task = asyncio.create_task(receive_from_ws())
    send_task = asyncio.create_task(send_to_ws())
    done, pending = await asyncio.wait([recv_task, send_task], return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    logger.info("WebSocket connection closed.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

