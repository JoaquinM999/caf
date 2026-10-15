import asyncio
import json
import logging
import os
from pathlib import Path
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

# Configure logging with both stream and file handlers
log_file = None
if getattr(sys, "frozen", False):
    log_file = Path(sys.executable).parent / "coucou-backend.log"
elif os.environ.get("LOCALAPPDATA"):
    log_file = Path(os.environ["LOCALAPPDATA"]) / "Coucou" / "coucou-backend.log"
else:
    log_file = Path("coucou-backend.log")

handlers = [logging.StreamHandler(sys.stdout) if sys.stdout else logging.NullHandler()]
try:
    fh = logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
    fh.setLevel(logging.INFO)
    handlers.append(fh)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=handlers,
    force=True,
)
logger = logging.getLogger("server")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from caf.engine import CafEngine
from caf.profiles_manager import get_available_profiles

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
        if engine is not None and engine.is_running and getattr(engine.profile, "nombre", "") == profile_name:
            logger.info(f"Caf engine already active with profile '{profile_name}'; keeping running.")
            return
        if engine is not None:
            engine.stop()
            if engine_task:
                engine_task.cancel()
                await asyncio.gather(engine_task, return_exceptions=True)
        engine = CafEngine(profile_name=profile_name, use_audio_hardware=True, events_queue=events)
        engine_task = asyncio.create_task(engine.start())
        engine_task.add_done_callback(_on_done)


import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

def load_audio_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                return cfg.get("audio", {})
        except Exception:
            pass
    return {}

def save_audio_config(input_idx, output_idx, headphones):
    cfg = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            pass
    audio_cfg = cfg.setdefault("audio", {})
    if input_idx is not None:
        audio_cfg["input_device"] = input_idx
    if output_idx is not None:
        audio_cfg["output_device"] = output_idx
    if headphones is not None:
        audio_cfg["headphones"] = headphones
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False)
    except Exception as e:
        logger.warning(f"No se pudo guardar config.yaml: {e}")

async def _parent_watchdog():
    parent_pid_str = os.getenv("COUCOU_PARENT_PID")
    if not parent_pid_str or not parent_pid_str.strip().isdigit():
        return
    parent_pid = int(parent_pid_str.strip())
    logger.info(f"Iniciando watchdog de Coucou (PID padre: {parent_pid})")
    while True:
        await asyncio.sleep(2.0)
        if sys.platform == "win32":
            import ctypes
            SYNCHRONIZE = 0x00100000
            h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, parent_pid)
            if not h:
                logger.info(f"El proceso padre Coucou ({parent_pid}) ha terminado. Cerrando backend de Caf automáticamente...")
                if engine:
                    engine.stop()
                os._exit(0)
            ctypes.windll.kernel32.CloseHandle(h)

async def _delayed_exit():
    await asyncio.sleep(0.3)
    if engine:
        engine.stop()
    os._exit(0)


@app.on_event("startup")
async def on_startup():
    logger.info("FastAPI startup: warming up Caf voice engine with profile 'amiguito'...")
    asyncio.create_task(_parent_watchdog())
    try:
        await start_engine("amiguito")
    except Exception as e:
        logger.error(f"Failed to auto-start engine on startup: {e!r}")


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


@app.get("/audio/devices")
def get_audio_devices():
    devices = CafEngine.list_audio_devices()
    cfg = load_audio_config()
    current_in = getattr(engine, "input_device_index", None) if engine else cfg.get("input_device")
    current_out = getattr(engine, "output_device_index", None) if engine else cfg.get("output_device")
    headphones = getattr(engine, "headphones", False) if engine else cfg.get("headphones", False)
    return {
        **devices,
        "current_input": current_in,
        "current_output": current_out,
        "headphones": headphones,
    }


@app.post("/audio/devices")
async def set_audio_devices(payload: dict):
    in_idx = payload.get("input_device")
    out_idx = payload.get("output_device")
    headphones = payload.get("headphones")
    save_audio_config(in_idx, out_idx, headphones)
    if engine:
        engine.set_audio_devices(in_idx, out_idx, headphones)
    return {"status": "ok", "message": "Dispositivos de audio actualizados exitosamente."}


@app.post("/shutdown")
async def shutdown():
    logger.info("Shutdown solicitado por el cliente Coucou.")
    asyncio.create_task(_delayed_exit())
    return {"status": "ok", "message": "Cerrando backend de Caf."}


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

