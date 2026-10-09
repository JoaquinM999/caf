# Caf V2 (Reconstrucción)

## Estructura de la solución
- **`backend/`**: Contiene la aplicación FastAPI `server.py` y el motor de Gemini Live `caf/engine.py`.
- **`windows/`**: Contiene el frontend en Tauri (Rust + TypeScript). El puente viejo de Vosk (`live.rs`) fue eliminado por completo, y ahora la comunicación fluye hacia el backend por WebSocket.

## Instrucciones de Arranque

Para iniciar el sistema completo necesitas dos terminales.

**1. Backend (Python)**
Desde la carpeta raíz del proyecto, ejecuta:
```bash
cd backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```
*(Nota: Asegúrate de tener el archivo `backend/.env` con tu `GEMINI_API_KEY`).*

**2. Frontend (Tauri)**
En otra terminal, ejecuta:
```bash
cd windows
npm run tauri dev
```
O, si quieres construir el ejecutable final de producción:
```bash
cd windows
npm run tauri build
```

## Pruebas Realizadas (Evidencia)
1. **Tests unitarios (FASE 1 y 2):** Se crearon y pasaron correctamente los tests de `backend/tests/test_tools.py` que verifican que la lista blanca de programas funciona, y que el *path traversal* es rechazado al manipular archivos.
2. **Test de integración (FASE 3):** Se ejecutó `backend/tests/test_integration.py` comprobando que `CafEngine` logra conectarse a la API Live de Gemini, emitiendo estados como `escuchando`, recibe texto simulado, y produce la respuesta de voz (`hablando`).
3. **Control de UI (FASE 4):** Se verificó que `CafClient` (en TS) cambia la UI de Mochi a "scanning/searching" (ejecutando herramienta) y "hablando" cuando recibe los eventos correspondientes por el WebSocket desde el servidor Python.
4. **Eliminación de Vosk:** Se suprimió la dependencia muerta en `src-tauri` para dejar Tauri como un cliente de frontend puro.

## Cosas Pendientes o No Automatizadas (Para probar a mano)
- **Audio de hardware real (Micrófono y Altavoces):** El `CafEngine` está configurado para usar `PyAudio` (en las threads concurrentes _hardware_audio_in_loop y _out_loop) pero no se puede asegurar su calidad sin hardware real y sin probar ecos en la computadora anfitriona.
- **Interrupción de voz del usuario:** Aunque el código escucha la señal `interrupted` de Gemini Live y vacía la cola de audio de salida para dejar de hablar, esto requiere que el usuario hable en el micrófono y experimente el corte en vivo para validar la sensibilidad.
- **Herramientas de PC destructivas:** La ejecución real de "abrir Spotify" (`explorer.exe shell:AppsFolder\Spotify...`) depende del entorno local de Windows. Las herramientas devuelven fallos controlados si no se encuentra la app.
