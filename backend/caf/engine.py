import asyncio
import os
import sys
import pyaudio
import traceback
import logging
from google import genai
from google.genai import types
from caf.profiles_manager import load_profile
import caf.tools as caf_tools

logger = logging.getLogger(__name__)

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE_IN = 16000
RATE_OUT = 24000
CHUNK = 1024

class CafEngine:
    def __init__(self, profile_name="amiguito", use_audio_hardware=True):
        from dotenv import load_dotenv
        from pathlib import Path
        import keyring
        
        load_dotenv(Path(__file__).parent.parent / ".env")
        
        # Primero intentar desde el Credential Manager de Windows (Configurado en UI)
        self.api_key = keyring.get_password("fr.louisraille.coucou", "caf-api-key")
        
        # Fallback al .env local
        if not self.api_key:
            self.api_key = os.getenv("GEMINI_API_KEY")
            
        if not self.api_key:
            raise ValueError("API Key no encontrada. Por favor agregá la clave de Caf en la configuración de Coucou o en el archivo .env")
            
        self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1alpha'})
        self.profile = load_profile(profile_name)
        
        self.use_audio_hardware = use_audio_hardware
        self.is_running = False
        
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue()
        self.text_in_queue = asyncio.Queue()
        self.events_queue = asyncio.Queue() # Para emitir estados al frontend
        
        self.model = "gemini-2.0-flash" # Fallback

    def _build_tools(self):
        declarations = []
        if "abrir_programa" in self.profile.herramientas:
            declarations.append(types.FunctionDeclaration(
                name="abrir_programa",
                description="Abre un programa en la PC. Solo puedes usar los que están en la lista blanca.",
                parameters=types.Schema(type="OBJECT", properties={"nombre": types.Schema(type="STRING")}, required=["nombre"])
            ))
        if "crear_archivo" in self.profile.herramientas:
            declarations.append(types.FunctionDeclaration(
                name="crear_archivo",
                description="Crea un archivo de texto en la carpeta de trabajo.",
                parameters=types.Schema(type="OBJECT", properties={"ruta_relativa": types.Schema(type="STRING"), "contenido": types.Schema(type="STRING")}, required=["ruta_relativa", "contenido"])
            ))
        if "leer_archivo" in self.profile.herramientas:
            declarations.append(types.FunctionDeclaration(
                name="leer_archivo",
                description="Lee el contenido de un archivo en la carpeta de trabajo.",
                parameters=types.Schema(type="OBJECT", properties={"ruta_relativa": types.Schema(type="STRING")}, required=["ruta_relativa"])
            ))
        if "listar_archivos" in self.profile.herramientas:
            declarations.append(types.FunctionDeclaration(
                name="listar_archivos",
                description="Lista los archivos en la carpeta de trabajo.",
                parameters=types.Schema(type="OBJECT", properties={"ruta_relativa": types.Schema(type="STRING", description="Directorio relativo, usualmente '.'")}, required=["ruta_relativa"])
            ))
        if "generar_reporte" in self.profile.herramientas:
            declarations.append(types.FunctionDeclaration(
                name="generar_reporte",
                description="Genera un reporte markdown.",
                parameters=types.Schema(type="OBJECT", properties={"titulo": types.Schema(type="STRING"), "contenido_markdown": types.Schema(type="STRING"), "formato": types.Schema(type="STRING")}, required=["titulo", "contenido_markdown"])
            ))
        if "borrar_archivo" in self.profile.herramientas:
            declarations.append(types.FunctionDeclaration(
                name="borrar_archivo",
                description="Borra un archivo en la carpeta de trabajo. ATENCION: Requiere confirmación.",
                parameters=types.Schema(type="OBJECT", properties={"ruta_relativa": types.Schema(type="STRING"), "confirmacion": types.Schema(type="STRING")}, required=["ruta_relativa"])
            ))
        if not declarations:
            return None
        return [{"function_declarations": declarations}]

    async def _handle_tool_call(self, function_call, session):
        logger.info(f"Tool solicitada: {function_call.name} {function_call.args}")
        self.events_queue.put_nowait({"estado": "ejecutando_herramienta", "detalle": function_call.name})
        try:
            if function_call.name == "abrir_programa": res = await asyncio.to_thread(caf_tools.abrir_programa, function_call.args.get("nombre", ""))
            elif function_call.name == "crear_archivo": res = await asyncio.to_thread(caf_tools.crear_archivo, function_call.args.get("ruta_relativa", ""), function_call.args.get("contenido", ""))
            elif function_call.name == "leer_archivo": res = await asyncio.to_thread(caf_tools.leer_archivo, function_call.args.get("ruta_relativa", ""))
            elif function_call.name == "listar_archivos": res = await asyncio.to_thread(caf_tools.listar_archivos, function_call.args.get("ruta_relativa", "."))
            elif function_call.name == "generar_reporte": res = await asyncio.to_thread(caf_tools.generar_reporte, function_call.args.get("titulo", ""), function_call.args.get("contenido_markdown", ""), function_call.args.get("formato", "md"))
            elif function_call.name == "borrar_archivo": res = await asyncio.to_thread(caf_tools.borrar_archivo, function_call.args.get("ruta_relativa", ""), function_call.args.get("confirmacion", "no"))
            else: res = f"Herramienta desconocida: {function_call.name}"
        except Exception as e:
            res = f"Error interno en herramienta: {str(e)}"
            
        logger.info(f"Tool resuelta: {res}")
        self.events_queue.put_nowait({"herramienta": {"nombre": function_call.name, "resultado": res}})
        await session.send(input=types.LiveClientToolResponse(
            function_responses=[types.FunctionResponse(id=function_call.id, name=function_call.name, response={"result": res})]
        ))

    def _hardware_audio_in_loop(self):
        p = getattr(self, "pa", None)
        if not p: return
        try:
            default_in = p.get_default_input_device_info()
            logger.info(f"🎤 [DEBUG] Usando micrófono: {default_in['name']} (índice {default_in['index']})")
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE_IN, input=True, frames_per_buffer=CHUNK, input_device_index=default_in['index'])
        except Exception as e:
            logger.error(f"Error abriendo microfono PyAudio: {e}")
            return
            
        import audioop
        import time
        last_log = time.time()
            
        while self.is_running:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                
                # Debug de volumen de entrada (1 vez por segundo si alguien habla)
                rms = audioop.rms(data, 2)
                if rms > 250 and time.time() - last_log > 1.0:
                    logger.info(f"🎤 [DEBUG] Audio captado (volumen: {rms})")
                    last_log = time.time()
                    
                self.audio_in_queue.put_nowait(data)
            except Exception as e:
                logger.error(f"Hardware In Error: {e}")
                break
        stream.stop_stream()
        stream.close()

    def _hardware_audio_out_loop(self):
        pass # Reemplazado por consumer

    async def _audio_out_consumer(self, stream_out):
        logger.info("🔊 [DEBUG] Iniciando hilo de reproducción de audio...")
        while self.is_running:
            data = await self.audio_out_queue.get()
            if data and stream_out:
                try:
                    logger.info(f"🔊 [DEBUG] Reproduciendo chunk de audio de {len(data)} bytes...")
                    await asyncio.to_thread(stream_out.write, data)
                except Exception as e:
                    logger.error(f"🔊 [DEBUG] Error al reproducir audio: {e}")

    async def start(self):
        self.is_running = True
        self.silence_frames = 0
        
        # Iniciar hardware threads if needed
        stream_out = None
        if self.use_audio_hardware:
            try:
                self.pa = pyaudio.PyAudio()
                asyncio.create_task(asyncio.to_thread(self._hardware_audio_in_loop))
                stream_out = self.pa.open(format=FORMAT, channels=CHANNELS, rate=RATE_OUT, output=True, frames_per_buffer=CHUNK)
                asyncio.create_task(self._audio_out_consumer(stream_out))
            except Exception as e:
                logger.error(f"Error abriendo parlantes PyAudio: {e}")
        
        system_prompt = self.profile.system_instruction + "\n\nResponde de manera natural y conversacional a lo que escuches."
        
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part.from_text(system_prompt)]),
            tools=self._build_tools()
        )
        
        attempt = 0
        while self.is_running:
            try:
                model_name = "gemini-3.8-live" if attempt == 0 else self.model
                self.events_queue.put_nowait({"estado": "reconectando", "detalle": model_name})
                async with self.client.aio.live.connect(model=model_name, config=config) as session:
                    logger.info(f"Conectado a {model_name}")
                    self.events_queue.put_nowait({"estado": "escuchando"})
                    attempt = 0
                    
                    async def sender():
                        while self.is_running:
                            try:
                                # Prioritize text
                                if not self.text_in_queue.empty():
                                    text = self.text_in_queue.get_nowait()
                                    await session.send(input=text, end_of_turn=True)
                                    self.events_queue.put_nowait({"transcripcion": {"rol": "usuario", "texto": text}})
                                    continue
                                
                                # Then audio
                                data = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.1)
                                import audioop
                                rms = audioop.rms(data, 2)
                                
                                # Si hay silencio continuo por 1.5s
                                if rms < 250:
                                    self.silence_frames += 1
                                else:
                                    self.silence_frames = 0
                                    
                                if self.silence_frames > int(16000 / 1024 * 1.5):
                                    # Ya mandamos el end_of_turn, ahora simplemente dropeamos los chunks de silencio
                                    continue
                                    
                                is_end = False
                                if self.silence_frames == int(16000 / 1024 * 1.5):
                                    is_end = True
                                    logger.info("🎙️ [DEBUG] Silencio detectado, forzando end_of_turn=True")
                                    
                                await session.send(input={"data": data, "mime_type": "audio/pcm;rate=16000"}, end_of_turn=is_end)
                            except asyncio.TimeoutError:
                                await asyncio.sleep(0.01)
                                
                    async def receiver():
                        has_indicated_audio = False
                        async for response in session.receive():
                            server_content = response.server_content
                            if server_content is not None:
                                if server_content.interrupted:
                                    # Vaciar cola de audio saliente
                                    while not self.audio_out_queue.empty():
                                        self.audio_out_queue.get_nowait()
                                    self.events_queue.put_nowait({"estado": "escuchando"})
                                
                                model_turn = server_content.model_turn
                                if model_turn:
                                    for part in model_turn.parts:
                                        if part.inline_data:
                                            self.audio_out_queue.put_nowait(part.inline_data.data)
                                            self.events_queue.put_nowait({"estado": "hablando"})
                                            if not has_indicated_audio:
                                                self.events_queue.put_nowait({"transcripcion": {"rol": "caf", "texto": "🔊 (Respondiendo por voz...)"}})
                                                has_indicated_audio = True
                                        if part.text:
                                            self.events_queue.put_nowait({"transcripcion": {"rol": "caf", "texto": part.text}})
                                            
                                if server_content.turn_complete:
                                    has_indicated_audio = False
                                            
                            if response.tool_call is not None:
                                for function_call in response.tool_call.function_calls:
                                    asyncio.create_task(self._handle_tool_call(function_call, session))
                                    
                    await asyncio.gather(sender(), receiver())
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en sesión Live: {e}")
                attempt += 1
                await asyncio.sleep(min(2 ** attempt, 30))
                
        if self.use_audio_hardware and stream_out:
            stream_out.stop_stream()
            stream_out.close()
            if hasattr(self, 'pa'):
                self.pa.terminate()

    def stop(self):
        self.is_running = False
