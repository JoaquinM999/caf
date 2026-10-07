import asyncio
import websockets
import json
import base64
import time

api_key = "AQ.Ab8RN6Jg_6FFDDW7zM6yiQfh-hUf3mLy6KAn3qerh70__an8Qw"
uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"

async def run_live():
    async with websockets.connect(uri) as ws:
        setup_msg = {
            "setup": {
                "model": "models/gemini-3.8-live",
                "generationConfig": {
                    "responseModalities": ["audio"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Puck"
                            }
                        }
                    }
                }
            }
        }
        await ws.send(json.dumps(setup_msg))
        
        setup_resp = await ws.recv()
        print("Setup Resp:", setup_resp)
        
        # Read speech
        with open(r"C:\Users\Joako\OneDrive\Escritorio\Coucou\test_speech.pcm", "rb") as f:
            speech_data = f.read()
        
        print("Sending speech...")
        chunk_size = 4000
        for i in range(0, len(speech_data), chunk_size):
            chunk = speech_data[i:i+chunk_size]
            b64 = base64.b64encode(chunk).decode("utf-8")
            req = {
                "realtimeInput": {
                    "mediaChunks": [{
                        "mimeType": "audio/pcm;rate=16000",
                        "data": b64
                    }]
                }
            }
            await ws.send(json.dumps(req))
            await asyncio.sleep(0.125)
            
        print("Sending silence...")
        silence = b"\x00" * chunk_size
        for _ in range(24):
            req = {
                "realtimeInput": {
                    "mediaChunks": [{
                        "mimeType": "audio/pcm;rate=16000",
                        "data": base64.b64encode(silence).decode("utf-8")
                    }]
                }
            }
            await ws.send(json.dumps(req))
            await asyncio.sleep(0.125)
            
        print("Waiting for response...")
        while True:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print("Gemini:", resp)
            except asyncio.TimeoutError:
                print("Timeout")
                break

asyncio.run(run_live())
