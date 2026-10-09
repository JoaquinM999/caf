import asyncio
import os
import pytest
from caf.engine import CafEngine
from caf.tools import _safe_resolve

@pytest.mark.asyncio
async def test_integration():
    print("Iniciando Integration Test...")
    engine = CafEngine(profile_name="amiguito", use_audio_hardware=False)
    
    # Arrancar el motor en background
    task = asyncio.create_task(engine.start())
    
    def on_done(t):
        if t.exception():
            import traceback
            print(f"Task crashed:")
            traceback.print_exception(type(t.exception()), t.exception(), t.exception().__traceback__)
    task.add_done_callback(on_done)
    
    # Esperar conexión
    print("Esperando conexión...")
    while True:
        event = await engine.events_queue.get()
        if event.get("estado") == "escuchando":
            break
            
    print("Conectado! Enviando texto de prueba...")
    engine.text_in_queue.put_nowait("Explicame la ley de Newton en dos frases")
    
    respuesta = False
    while True:
        try:
            event = await asyncio.wait_for(engine.events_queue.get(), timeout=10)
            if event.get("estado") == "hablando":
                print(f"Caf respondió (Audio recibido)")
                respuesta = True
                break
        except asyncio.TimeoutError:
            print("Timeout esperando respuesta de Newton")
            break
            
    print("Prueba Newton terminada. Enviando texto para tool...")
    engine.text_in_queue.put_nowait("URGENTE: Usa la herramienta crear_archivo para crear un archivo que se llame prueba_test.txt con el contenido 'hola mundo real'. No digas nada, solo ejecuta la herramienta.")
    
    tool_ejecutada = False
    while True:
        try:
            event = await asyncio.wait_for(engine.events_queue.get(), timeout=20)
            if "herramienta" in event and event["herramienta"]["nombre"] == "crear_archivo":
                print(f"Herramienta ejecutada: {event['herramienta']}")
                tool_ejecutada = True
                break
        except asyncio.TimeoutError:
            print(f"Timeout esperando tool.")
            break
            
    # Verificar archivo
    target = _safe_resolve("prueba_test.txt")
    if target.exists():
        print(f"¡EXITO! El archivo existe con contenido: {target.read_text()}")
        target.unlink()
    else:
        print("Fallo: el archivo no fue creado.")
        
    engine.stop()
    task.cancel()
    
if __name__ == "__main__":
    asyncio.run(test_integration())
