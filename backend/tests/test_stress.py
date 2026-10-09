import asyncio
import pytest
from caf.engine import CafEngine

@pytest.mark.asyncio
async def test_stress_reconnect():
    print("Iniciando prueba de resistencia y reconexión...")
    engine = CafEngine(profile_name="amiguito", use_audio_hardware=False)
    task = asyncio.create_task(engine.start())
    
    # 1. Esperar conexión
    while True:
        event = await engine.events_queue.get()
        if event.get("estado") == "escuchando":
            print("Conectado inicialmente.")
            break
            
    print("Enviando mensaje 1")
    engine.text_in_queue.put_nowait("Mensaje 1. Decí OK.")
    
    # 2. Forzar desconexión sucia rompiendo el cliente temporalmente
    print("Forzando desconexión (hack)")
    engine.client = None # Forzará excepción en la siguiente vuelta o recepción
    
    # Wait for the reconnect event
    reconnected = False
    for _ in range(50):
        try:
            event = await asyncio.wait_for(engine.events_queue.get(), timeout=1.0)
            if event.get("estado") == "reconectando":
                # Restore the client
                import os
                from google import genai
                engine.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={'api_version': 'v1alpha'})
            elif event.get("estado") == "escuchando":
                print("¡Reconexión exitosa comprobada!")
                reconnected = True
                break
        except asyncio.TimeoutError:
            pass
            
    engine.stop()
    task.cancel()
    
    assert reconnected, "El motor no logró reconectarse tras un fallo simulado"
