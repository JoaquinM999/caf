from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import asyncio
import json
import logging
import base64
from caf.engine import CafEngine
from caf.profiles_manager import get_available_profiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

app = FastAPI(title="Caf V2 Backend")

engine = None
engine_task = None

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Caf V2 Backend is running."}

@app.get("/profiles")
def get_profiles():
    return {"profiles": get_available_profiles()}

@app.post("/profiles/change")
async def change_profile(profile_name: str):
    global engine, engine_task
    if engine and engine.is_running:
        engine.stop()
        if engine_task:
            engine_task.cancel()
    
    engine = CafEngine(profile_name=profile_name, use_audio_hardware=True)
    engine_task = asyncio.create_task(engine.start())
    return {"status": "ok", "message": f"Profile changed to {profile_name}"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global engine, engine_task
    
    await websocket.accept()
    logger.info("WebSocket connected.")
    
    if not engine or not engine.is_running:
        engine = CafEngine(profile_name="amiguito", use_audio_hardware=True)
        engine_task = asyncio.create_task(engine.start())
        def on_done(t):
            if t.exception():
                logger.error(f"ENGINE CRASHED: {t.exception()}")
                import traceback
                traceback.print_exception(type(t.exception()), t.exception(), t.exception().__traceback__)
        engine_task.add_done_callback(on_done)
        
    async def receive_from_ws():
        try:
            while True:
                data = await websocket.receive()
                if "text" in data:
                    try:
                        msg = json.loads(data["text"])
                        action = msg.get("action")
                        if action == "hablar":
                            text = msg.get("text")
                            if text:
                                engine.text_in_queue.put_nowait(text)
                        elif action == "cambiar_perfil":
                            # TODO: handle cleanly without breaking ws loop
                            pass
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON received: {data['text']}")
                elif "bytes" in data:
                    # Received raw audio from frontend
                    engine.audio_in_queue.put_nowait(data["bytes"])
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected.")
        except Exception as e:
            logger.error(f"WS receive error: {e}")

    async def send_to_ws():
        try:
            while True:
                # Prioritize events
                if not engine.events_queue.empty():
                    event = engine.events_queue.get_nowait()
                    await websocket.send_text(json.dumps(event))
                    continue
                
                # Check for audio out
                try:
                    audio_data = await asyncio.wait_for(engine.audio_out_queue.get(), timeout=0.05)
                    # Send audio as binary
                    await websocket.send_bytes(audio_data)
                except asyncio.TimeoutError:
                    pass
                
                # Yield to not starve the loop if neither queue has data
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"WS send error: {e}")

    # Run both loops until one exits
    recv_task = asyncio.create_task(receive_from_ws())
    send_task = asyncio.create_task(send_to_ws())
    
    done, pending = await asyncio.wait([recv_task, send_task], return_when=asyncio.FIRST_COMPLETED)
    
    for task in pending:
        task.cancel()
        
    logger.info("WebSocket connection closed.")
