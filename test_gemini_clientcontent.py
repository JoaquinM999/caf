import asyncio
import websockets
import json
import base64

api_key = "AQ.Ab8RN6Jg_6FFDDW7zM6yiQfh-hUf3mLy6KAn3qerh70__an8Qw"
uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"

async def run_live():
    async with websockets.connect(uri) as ws:
        setup_msg = {
            "setup": {
                "model": "models/gemini-3.8-live",

                "realtimeInputConfig": {
                    "automaticActivityDetection": {
                        "disabled": True
                    }
                }
            }
        }
        await ws.send(json.dumps(setup_msg))
        print("Setup Resp:", await ws.recv())
        
        print("Sending audio from file...")
        with open(r"C:\Users\Joako\OneDrive\Escritorio\Coucou\test_speech.pcm", "rb") as f:
            speech = f.read()
            
        req = {
            "clientContent": {
                "turns": [{
                    "role": "user",
                    "parts": [{"inlineData": {"mimeType": "audio/pcm;rate=16000", "data": base64.b64encode(speech).decode("utf-8")}}]
                }],
                "turnComplete": False
            }
        }
        await ws.send(json.dumps(req))
        await asyncio.sleep(0.5)
        
        print("Sending TURN_COMPLETE...")
        req2 = {
            "clientContent": {
                "turnComplete": True
            }
        }
        await ws.send(json.dumps(req2))
        
        with open("output.pcm", "wb") as f_out:
            while True:
                resp = await ws.recv()
                if len(resp) > 500:
                    print(f"Resp: [Large payload: {len(resp)} bytes]")
                    try:
                        data = json.loads(resp)
                        parts = data.get("serverContent", {}).get("modelTurn", {}).get("parts", [])
                        for p in parts:
                            b64 = p.get("inlineData", {}).get("data")
                            if b64:
                                f_out.write(base64.b64decode(b64))
                    except:
                        pass
                else:
                    print(f"Resp: {resp}")

asyncio.run(run_live())
