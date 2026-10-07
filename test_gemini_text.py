import asyncio
import websockets
import json

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
        
        req = {
            "clientContent": {
                "turns": [{
                    "role": "user",
                    "parts": [{"text": "Hola, respondeme esto por favor."}]
                }],
                "turnComplete": True
            }
        }
        print("Sending text request...")
        await ws.send(json.dumps(req))
            
        print("Waiting for response...")
        while True:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print("Gemini:", resp[:100] + b"..." if len(resp) > 100 else resp)
            except asyncio.TimeoutError:
                print("Timeout")
                break

asyncio.run(run_live())
