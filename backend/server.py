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

# Configure logging without duplicating lines when stdout is already redirected to coucou-backend.log
log_file = None
if getattr(sys, "frozen", False):
    log_file = Path(sys.executable).parent / "coucou-backend.log"
elif os.environ.get("LOCALAPPDATA"):
    log_file = Path(os.environ["LOCALAPPDATA"]) / "Coucou" / "coucou-backend.log"
else:
    log_file = Path("coucou-backend.log")

handlers = []
if not getattr(sys, "frozen", False) and sys.stdout:
    handlers.append(logging.StreamHandler(sys.stdout))
try:
    fh = logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
    fh.setLevel(logging.INFO)
    handlers.append(fh)
except Exception:
    if sys.stdout and not handlers:
        handlers.append(logging.StreamHandler(sys.stdout))
if not handlers:
    handlers.append(logging.NullHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=handlers,
    force=True,
)
logger = logging.getLogger("server")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from caf.engine import CafEngine
from caf.profiles_manager import get_available_profiles

app = FastAPI(title="Caf V2 Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


async def start_engine(profile_name: str, force_restart: bool = False):
    """(Re)inicia el motor con un perfil. Detiene el anterior primero."""
    global engine, engine_task
    async with _lock:
        if not force_restart and engine is not None and engine.is_running and getattr(engine.profile, "nombre", "") == profile_name:
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

def get_config_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for cand in (exe_dir / "config.yaml", exe_dir.parents[2] / "backend" / "config.yaml"):
            if cand.exists():
                return cand
        return exe_dir / "config.yaml"
    return Path(__file__).resolve().parent / "config.yaml"

CONFIG_PATH = get_config_path()

def load_audio_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                return cfg.get("audio", {})
        except Exception:
            pass
    return {}

def save_audio_config(input_idx, output_idx, headphones, auto_headphones=None):
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
    else:
        audio_cfg.pop("input_device", None)
    if output_idx is not None:
        audio_cfg["output_device"] = output_idx
    else:
        audio_cfg.pop("output_device", None)
    if headphones is not None:
        audio_cfg["headphones"] = headphones
    if auto_headphones is not None:
        audio_cfg["auto_headphones"] = auto_headphones
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


# ── Puente RPC con la Isla de Coucou ─────────────────────────────────────────

_pending_island_asks = {}
_ask_seq = 0
_connected_websockets: set = set()
_main_loop = None

async def _ask_island_async(kind: str, input_data: dict) -> str:
    global _ask_seq
    if not _connected_websockets:
        return "Error: la Isla de Coucou no está conectada por WebSocket."
    _ask_seq += 1
    req_id = _ask_seq
    fut = asyncio.get_running_loop().create_future()
    _pending_island_asks[req_id] = fut
    try:
        payload = {"island_ask": {"id": req_id, "kind": kind, "input": input_data}}
        text_data = json.dumps(payload)
        delivered = False
        for ws in list(_connected_websockets):
            try:
                await ws.send_text(text_data)
                delivered = True
            except Exception:
                _connected_websockets.discard(ws)
        if not delivered:
            return "Error: no se pudo enviar la consulta a la Isla de Coucou."
        return await asyncio.wait_for(fut, timeout=6.0)
    except asyncio.TimeoutError:
        return f"Error: la Isla de Coucou tardó más de 6s en responder ({kind})."
    except Exception as e:
        return f"Error consultando la Isla: {e}"
    finally:
        _pending_island_asks.pop(req_id, None)

def _island_ask_sync_bridge(kind: str, input_data: dict) -> str:
    global _main_loop
    if _main_loop is None or not _main_loop.is_running():
        return "Error: loop de eventos no disponible."
    try:
        fut = asyncio.run_coroutine_threadsafe(_ask_island_async(kind, input_data), _main_loop)
        return fut.result(timeout=7.0)
    except Exception as e:
        return f"Error en puente con la Isla: {e}"

import caf.tools as caf_tools
caf_tools.set_island_ask_handler(_island_ask_sync_bridge)


@app.on_event("startup")
async def on_startup():
    global _main_loop
    _main_loop = asyncio.get_running_loop()
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
    auto_hp = cfg.get("auto_headphones", True)
    inputs_list = devices.get("inputs", [])
    outputs_list = devices.get("outputs", [])
    hp_in = next((d["index"] for d in inputs_list if any(w in d["name"].lower() for w in ("airpod", "auricular", "headphone", "headset", "buds", "hands-free"))), None)
    hp_out = next((d["index"] for d in outputs_list if any(w in d["name"].lower() for w in ("airpod", "auricular", "headphone", "headset", "buds", "hands-free"))), None)
    return {
        "inputs": inputs_list,
        "outputs": outputs_list,
        "input_devices": inputs_list,
        "output_devices": outputs_list,
        "default_input": devices.get("default_input"),
        "default_output": devices.get("default_output"),
        "current_input": current_in,
        "current_output": current_out,
        "current_input_index": current_in,
        "current_output_index": current_out,
        "headphones": headphones,
        "auto_headphones": auto_hp,
        "detected_headphones": {"input": hp_in, "output": hp_out},
    }


@app.post("/audio/devices")
async def set_audio_devices(payload: dict):
    in_idx = payload.get("input_device") if "input_device" in payload else payload.get("input_device_index")
    out_idx = payload.get("output_device") if "output_device" in payload else payload.get("output_device_index")
    headphones = payload.get("headphones")
    auto_hp = payload.get("auto_headphones")
    save_audio_config(in_idx, out_idx, headphones, auto_hp)
    if engine:
        engine.set_audio_devices(in_idx, out_idx, headphones)
    return {"status": "ok", "message": "Dispositivos de audio actualizados exitosamente."}


@app.get("/config")
def get_config():
    profile = getattr(engine, "profile", None)
    cur_voice = getattr(engine, "voice", "") or (getattr(profile, "voz", "Aoede") if profile else "Aoede")
    cur_model = getattr(engine, "model", "") or "gemini-3.8-live"
    cur_profile = getattr(profile, "nombre", "amiguito") if profile else "amiguito"
    wake_en = getattr(engine, "wake_enabled", False)
    headphones = getattr(engine, "headphones", False)
    return {
        "voice": cur_voice,
        "model": cur_model,
        "profile": cur_profile,
        "wake_enabled": wake_en,
        "headphones": headphones,
        "available_voices": ["Aoede", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"],
        "available_models": [
            {"id": "gemini-3.8-live", "name": "Gemini 3.8 Live (Predeterminado)", "desc": "Velocidad máxima, audio bidireccional fluido de menor latencia"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash Live", "desc": "Ultrarrápido, versátil y equilibrado"},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro Live", "desc": "Máxima capacidad analítica para razonamiento profundo"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash Live", "desc": "Ligero y de respuesta ágil"}
        ],
        "available_profiles": get_available_profiles(),
    }


@app.post("/config")
async def update_config(payload: dict):
    restart_needed = False
    if "voice" in payload and payload["voice"]:
        v = payload["voice"].strip()
        cfg = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception:
                pass
        cfg["voice"] = v
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, default_flow_style=False)
        except Exception as e:
            logger.warning(f"No se pudo guardar voice en config.yaml: {e}")
        if engine and getattr(engine, "voice", "") != v:
            engine.voice = v
            restart_needed = True

    if "model" in payload and payload["model"]:
        m = payload["model"].strip()
        cfg = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception:
                pass
        cfg["model"] = m
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, default_flow_style=False)
        except Exception as e:
            logger.warning(f"No se pudo guardar model en config.yaml: {e}")
        if engine and getattr(engine, "model", "") != m:
            engine.model = m
            restart_needed = True

    if "wake_enabled" in payload and engine:
        engine.wake_enabled = bool(payload["wake_enabled"])
        if not engine.wake_enabled and engine.mode == "dormido":
            engine.request_wake()

    if "api_key" in payload and payload["api_key"]:
        os.environ["GEMINI_API_KEY"] = payload["api_key"]
        restart_needed = True

    if restart_needed and engine:
        cur_prof = getattr(engine.profile, "nombre", "amiguito")
        await start_engine(cur_prof, force_restart=True)

    return {"status": "ok", "message": "Configuración de Caf actualizada exitosamente."}


@app.get("/stats")
def get_stats():
    from caf.stats import load_stats
    from caf.memory import cargar_recuerdos
    return {
        "status": "ok",
        "stats": load_stats(),
        "memory_count": len(cargar_recuerdos())
    }


@app.get("/memory")
def get_memory():
    from caf.memory import cargar_recuerdos
    return {"recuerdos": cargar_recuerdos()}


@app.post("/memory")
def add_memory(payload: dict):
    from caf.memory import guardar_recuerdo, cargar_recuerdos
    r = payload.get("recuerdo", "").strip()
    if not r:
        return {"status": "error", "message": "Falta el texto a recordar."}
    res = guardar_recuerdo(r)
    return {"status": "ok", "message": res, "recuerdos": cargar_recuerdos()}


@app.delete("/memory")
def delete_memory(payload: dict):
    from caf.memory import olvidar_recuerdo, cargar_recuerdos
    r = payload.get("recuerdo", "").strip()
    if not r:
        return {"status": "error", "message": "Falta el texto a olvidar."}
    res = olvidar_recuerdo(r)
    return {"status": "ok", "message": res, "recuerdos": cargar_recuerdos()}


@app.post("/shutdown")
async def shutdown():
    logger.info("Shutdown solicitado por el cliente Coucou.")
    asyncio.create_task(_delayed_exit())
    return {"status": "ok", "message": "Cerrando backend de Caf."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connected_websockets.add(websocket)
    logger.info(f"WebSocket connected. Total activos: {len(_connected_websockets)}")

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
                elif action == "island_reply":
                    req_id = msg.get("id")
                    fut = _pending_island_asks.get(req_id)
                    if fut and not fut.done():
                        fut.set_result(str(msg.get("result", "")))
        except WebSocketDisconnect:
            pass
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

    try:
        recv_task = asyncio.create_task(receive_from_ws())
        send_task = asyncio.create_task(send_to_ws())
        done, pending = await asyncio.wait([recv_task, send_task], return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    finally:
        _connected_websockets.discard(websocket)
        logger.info(f"WebSocket connection closed. Total activos restantes: {len(_connected_websockets)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

