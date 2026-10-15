"""Motor de voz de Caf V2 (Gemini Live, audio bidireccional).

Cambios clave respecto de la version anterior:
- SDK google-genai actual (send_realtime_input / send_tool_response).
- Sin `audioop` (no existe en Python 3.13+).
- receive() devuelve UN turno: se llama en bucle.
- Sin fallback a un modelo que no es Live.
- Un unico consumidor de audio de salida (los parlantes locales).
- Reconexion con backoff real y reanudacion de sesion.
"""
import asyncio
import logging
import os
import time
from array import array
from collections import deque
from pathlib import Path

import pyaudio
from google import genai
from google.genai import types

import caf.tools as caf_tools
from caf.profiles_manager import load_profile

logger = logging.getLogger(__name__)

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE_IN = 16000   # lo que se manda a Gemini
RATE_OUT = 24000  # lo que devuelve Gemini
CHUNK = 1024

MODEL = os.getenv("CAF_MODEL", "gemini-3.8-live")
TOOL_TIMEOUT = 20  # segundos

# nombre -> descripcion, parametros (todos STRING), requeridos, funcion
TOOLS = {
    "abrir_programa": dict(
        desc="Abre cualquier programa, aplicación o juego instalado en la PC (ej. Chrome, Spotify, Discord, VS Code, Steam, Calculadora, Photoshop, Bloc de notas, etc.).",
        params={"nombre": "Nombre del programa o aplicación a abrir"},
        required=["nombre"], fn=caf_tools.abrir_programa),
    "crear_archivo": dict(
        desc="Crea un archivo de texto en la carpeta de trabajo.",
        params={"ruta_relativa": "Ruta relativa, ej. 'notas/hola.txt'", "contenido": "Texto del archivo"},
        required=["ruta_relativa", "contenido"], fn=caf_tools.crear_archivo),
    "leer_archivo": dict(
        desc="Lee un archivo de la carpeta de trabajo.",
        params={"ruta_relativa": "Ruta relativa del archivo"},
        required=["ruta_relativa"], fn=caf_tools.leer_archivo),
    "listar_archivos": dict(
        desc="Lista los archivos de la carpeta de trabajo.",
        params={"ruta_relativa": "Directorio relativo, por defecto '.'"},
        required=[], fn=caf_tools.listar_archivos),
    "generar_reporte": dict(
        desc="Genera un reporte en markdown en la carpeta de trabajo.",
        params={"titulo": "Titulo del reporte", "contenido_markdown": "Contenido en markdown",
                "formato": "'md' o 'txt'"},
        required=["titulo", "contenido_markdown"], fn=caf_tools.generar_reporte),
    "spotify_reproducir": dict(
        desc="Reproduce una cancion o tema en Spotify directamente.",
        params={"consulta": "Cancion y artista, ej. 'YSY A Oro y Platino'"},
        required=["consulta"], fn=caf_tools.spotify_reproducir),
    "spotify_pausar": dict(
        desc="Pausa o reanuda la reproduccion actual de musica en Spotify.",
        params={},
        required=[], fn=caf_tools.spotify_pausar),
    "spotify_siguiente": dict(
        desc="Pasa a la siguiente cancion o tema en Spotify.",
        params={},
        required=[], fn=caf_tools.spotify_siguiente),
    "spotify_anterior": dict(
        desc="Vuelve a la cancion o tema anterior en Spotify.",
        params={},
        required=[], fn=caf_tools.spotify_anterior),
    "youtube_reproducir": dict(
        desc="Busca en YouTube y reproduce el primer resultado. Si piden el 'último video' o el más reciente, busca automáticamente el más recientemente subido.",
        params={"consulta": "Qué buscar o canal/artista"},
        required=["consulta"], fn=caf_tools.youtube_reproducir),
    "recordar": dict(
        desc="Guarda una instrucción, dato o preferencia en la memoria permanente de Caf para recordarla siempre (ej. 'siempre que pida el último video buscar por fecha de subida', 'mi nombre es Joaquín').",
        params={"recuerdo": "La instrucción, dato o preferencia a recordar para siempre"},
        required=["recuerdo"], fn=caf_tools.recordar),
    "listar_recuerdos": dict(
        desc="Muestra lo que Caf tiene guardado en su memoria persistente.",
        params={}, required=[], fn=caf_tools.listar_recuerdos),
    "olvidar": dict(
        desc="Elimina un dato de la memoria permanente de Caf si el usuario lo pide.",
        params={"recuerdo": "Texto o tema a olvidar"},
        required=["recuerdo"], fn=caf_tools.olvidar),
    "buscar_web": dict(
        desc="Busca en internet y devuelve los primeros resultados (titulo, resumen y direccion).",
        params={"consulta": "Que buscar"},
        required=["consulta"], fn=caf_tools.buscar_web),
    "leer_pagina": dict(
        desc="Lee el texto de una pagina web (http/https) para resumirla o sacar datos.",
        params={"url": "Direccion completa de la pagina"},
        required=["url"], fn=caf_tools.leer_pagina),
    "abrir_url": dict(
        desc="Abre una pagina web (http o https) en el navegador.",
        params={"url": "Direccion completa, ej. https://es.wikipedia.org"},
        required=["url"], fn=caf_tools.abrir_url),
    "desactivar_asistente": dict(
        desc=("Pone a Caf en modo espera (dormido). Usala cuando el usuario se despida o diga que te desactives: "
              "'gracias Caf, ya podes desactivarte', 'chau Caf', 'dormi'. Despues despedite con una frase muy corta."),
        params={}, required=[], fn=None),  # la maneja el motor
    "borrar_archivo": dict(
        desc="Borra un archivo de la carpeta de trabajo. Requiere confirmacion explicita del usuario ('si').",
        params={"ruta_relativa": "Ruta relativa del archivo", "confirmacion": "'si' solo si el usuario lo confirmo"},
        required=["ruta_relativa"], fn=caf_tools.borrar_archivo),
}


def _rms(data: bytes) -> int:
    """Volumen RMS de un buffer Int16 (reemplazo de audioop.rms)."""
    a = array("h")
    a.frombytes(data[: len(data) - (len(data) % 2)])
    if not a:
        return 0
    return int((sum(x * x for x in a) / len(a)) ** 0.5)


class NoiseGate:
    """Compuerta de ruido adaptativa (ventilador, murmullo de fondo).

    Mide el piso de ruido y solo deja pasar el audio cuando el volumen lo supera
    claramente. Lo que queda por debajo se reemplaza por silencio digital, asi el
    detector de voz del servidor ve silencio limpio y cierra bien los turnos.
    """

    def __init__(self, min_open=70, ratio=2.5, hang_ms=750, preroll=6, open_after=1):
        self.min_open = min_open
        self.ratio = ratio
        self.hang_chunks = max(1, int(hang_ms / (1000 * CHUNK / RATE_IN)))
        self.open_after = open_after
        self.pre = deque(maxlen=preroll)
        self.floor = 60.0
        self.open = False
        self.hang = 0
        self.hits = 0
        self.last_rms = 0
        self.threshold = min_open

    def process(self, data: bytes):
        rms = _rms(data)
        self.last_rms = rms
        self.threshold = max(self.min_open, self.floor * self.ratio)
        loud = rms > self.threshold
        if self.open:
            self.hang = self.hang_chunks if loud else self.hang - 1
            if self.hang <= 0:
                self.open = False
                self.hits = 0
            return [data]
        self.pre.append(data)
        if loud:
            self.hits += 1
        else:
            self.hits = 0
            self.floor = 0.97 * self.floor + 0.03 * rms  # aprende el ruido ambiente
        if self.hits >= self.open_after:
            self.open = True
            self.hang = self.hang_chunks
            out = list(self.pre)  # pre-roll: no cortar el comienzo de la frase
            self.pre.clear()
            return out
        return [bytes(len(data))]  # silencio digital


def find_api_key() -> str:
    import sys
    from dotenv import load_dotenv

    # 1. Environment variables already in memory
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip():
        return key.strip()

    # 2. Keyring (from Coucou Settings UI)
    try:
        import keyring
        for entry_name in ("caf-api-key", "google-api-key"):
            k = keyring.get_password("fr.louisraille.coucou", entry_name)
            if k and k.strip():
                return k.strip()
    except Exception:
        pass

    # 3. Check possible .env paths
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.extend([exe_dir / ".env", exe_dir / "backend" / ".env"])

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Coucou" / ".env")
    app_data = os.environ.get("APPDATA")
    if app_data:
        candidates.append(Path(app_data) / "Coucou" / ".env")
    home = Path.home()
    candidates.extend([home / ".caf" / ".env", home / ".coucou" / ".env", home / ".env"])

    here = Path(__file__).resolve()
    for base in (here.parents[1], here.parents[2] if len(here.parents) > 2 else here.parent):
        candidates.extend([base / ".env", base / "Caf" / ".env", base / "backend" / ".env"])
    candidates.extend([Path.cwd() / ".env", Path.cwd() / "backend" / ".env"])

    for env_file in candidates:
        if env_file.exists():
            load_dotenv(env_file, override=False)
            k = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if k and k.strip():
                return k.strip()

    # 4. Windows Registry HKCU\Environment (User environment variables)
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg_key:
                for reg_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    try:
                        val, _ = winreg.QueryValueEx(reg_key, reg_name)
                        if val and val.strip():
                            return val.strip()
                    except FileNotFoundError:
                        pass
        except Exception:
            pass

    return ""


class CafEngine:
    def __init__(self, profile_name="amiguito", use_audio_hardware=True, events_queue=None):
        api_key = find_api_key()
        if not api_key:
            raise ValueError("API Key no encontrada: configúrala en Ajustes de Coucou (Caf) o en el archivo .env (GEMINI_API_KEY).")

        self.client = genai.Client(api_key=api_key)  # sin forzar v1alpha
        self.profile = load_profile(profile_name)
        self.use_audio_hardware = use_audio_hardware
        # Con auriculares (CAF_HEADPHONES=1) el mic queda abierto mientras Caf habla.
        # Sin auriculares se silencia el mic para que no se escuche a si mismo.
        self.headphones = os.getenv("CAF_HEADPHONES", "0") == "1"

        self.is_running = False
        self.audio_in_queue = asyncio.Queue(maxsize=100)
        self.audio_out_queue = asyncio.Queue()
        self.text_in_queue = asyncio.Queue()
        self.events_queue = events_queue if events_queue is not None else asyncio.Queue()

        self._loop = None
        self._pa = None
        self._stream_in = None
        self._stream_out = None
        self._resume_handle = None
        self._estado = None
        self._playing = False
        self._mute_until = 0.0

        # Filtrado de ruido y push-to-talk (ver README en los comentarios de abajo)
        self.gate = NoiseGate(
            min_open=int(os.getenv("CAF_GATE_MIN", "70")),
            ratio=float(os.getenv("CAF_GATE_RATIO", "2.5")),
            open_after=int(os.getenv("CAF_GATE_HITS", "1")),
            preroll=int(os.getenv("CAF_GATE_PREROLL", "6")),
        ) if os.getenv("CAF_GATE", "1") == "1" else None
        self.ptt_enabled = os.getenv("CAF_PTT", "0") == "1"
        self.muted = False
        self._ptt_down = False
        self._ptt_tail = 0
        self._ptt_hooks = []
        self._last_gate_log = 0.0

        # Modo espera con palabra de activacion local ("Caf"). Si falta Vosk o el modelo, queda siempre activo.
        self.wake = None
        self.wake_enabled = False
        self.idle_seconds = float(os.getenv("CAF_IDLE_SECONDS", "60"))
        self._preroll = deque(maxlen=int(2.5 * RATE_IN / CHUNK))  # ~2,5 s de audio previo a la activacion
        self._last_activity = time.monotonic()
        self._sleep_after_speech = False
        self._sleep_deadline = 0.0
        self._wake_requested = False
        if os.getenv("CAF_WAKE", "1") == "1" and use_audio_hardware and not self.ptt_enabled:
            try:
                from caf.wake import WakeWord, find_model_path
                model_path = find_model_path()
                if model_path is None:
                    logger.warning("No encontre el modelo de Vosk (carpeta modelo_vosk): sin modo espera. "
                                   "Definí CAF_VOSK_MODEL con la ruta.")
                else:
                    self.wake = WakeWord(model_path)
                    self.wake_enabled = True
            except Exception as e:
                logger.warning(f"Palabra de activacion no disponible ({e}): sin modo espera.")
        self.mode = "dormido" if self.wake_enabled else "activo"

    # ---------------------------------------------------------------- eventos
    def _emit(self, event: dict):
        self.events_queue.put_nowait(event)

    def _set_estado(self, estado: str, detalle: str = ""):
        if estado != self._estado or detalle:
            self._estado = estado
            self._emit({"estado": estado, "detalle": detalle} if detalle else {"estado": estado})

    # ---------------------------------------------------------------- config
    def _build_tools(self):
        decls = []
        names = list(self.profile.herramientas)
        if self.wake_enabled and "desactivar_asistente" not in names:
            names.append("desactivar_asistente")  # siempre disponible en modo espera
        for name in names:
            if name == "google_search":
                continue
            spec = TOOLS.get(name)
            if not spec:
                logger.warning(f"Herramienta '{name}' del perfil no existe, se ignora.")
                continue
            decl = dict(name=name, description=spec["desc"])
            if spec["params"]:
                decl["parameters"] = types.Schema(
                    type="OBJECT",
                    properties={k: types.Schema(type="STRING", description=d) for k, d in spec["params"].items()},
                    required=spec["required"] or None,
                )
            decls.append(types.FunctionDeclaration(**decl))
        tools = []
        if "google_search" in self.profile.herramientas and os.getenv("CAF_SEARCH", "0") == "1":
            tools.append(types.Tool(google_search=types.GoogleSearch()))  # buscar en internet
        if decls:
            tools.append(types.Tool(function_declarations=decls))
        return tools or None

    def _build_config(self):
        from caf.memory import obtener_prompt_memoria
        prompt = self.profile.system_instruction + """

REGLAS GENERALES (valen siempre):
- Si el usuario te llama por tu nombre ("Caf") sin pedir nada más, contestá solamente: "Sí, decime qué necesitás." y esperá atentamente.
- Llamá a la herramienta desactivar_asistente SOLO si el usuario pide explícitamente que te desactives, te duermas o se despide ("ya podés desactivarte", "chau Caf", "dormí", "hasta luego"). Un simple "gracias" NO es una despedida: contestá brevemente con amabilidad ("De nada", "A la orden") y seguí atento. Jamás digas cosas como "en ningún momento te llamé" ni te disculpes innecesariamente.
- Si te piden reproducir música o abrir una canción (ej. en Spotify o YouTube), ejecutá la herramienta inmediatamente y confirmá de manera breve y positiva ("Dale, te pongo [canción]").
- Si el usuario te pide que recuerdes algo ("recordá que...", "acordate de...", "guardá en tu memoria...", "de ahora en adelante siempre..."), ejecutá la herramienta 'recordar' inmediatamente para guardarlo en tu memoria persistente.
- El usuario a veces piensa en voz alta: dice "eh...", hace pausas o deja frases a medio decir. Esperá pacientemente a que termine su pedido antes de interrumpir.
- Si te piden información actual (noticias, datos, precios, clima, resultados), usá buscar_web (y leer_pagina si hace falta más detalle) y respondé con un resumen corto.
- Respondé de manera natural, concisa y conversacional a lo que escuches.""" + obtener_prompt_memoria()
        kwargs = dict(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=prompt)]),
            tools=self._build_tools(),
        )
        # NO usar thinking_config / thinking_level con gemini-3.8-live.
        if os.getenv("CAF_MINIMAL", "0") != "1":
            kwargs.update(
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.profile.voz))),
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                context_window_compression=types.ContextWindowCompressionConfig(
                    sliding_window=types.SlidingWindow()),
                session_resumption=types.SessionResumptionConfig(handle=self._resume_handle),
                realtime_input_config=types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                        # LOW = tarda mas en dar por terminada la frase (tolera "eh..." y pausas largas)
                        end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                        prefix_padding_ms=100,
                        silence_duration_ms=int(os.getenv("CAF_SILENCE_MS", "1800")),
                    )),
            )
            if os.getenv("CAF_PROACTIVE", "0") == "1":
                # El modelo puede decidir NO responder si lo que oye no es para el.
                kwargs["proactivity"] = types.ProactivityConfig(proactive_audio=True)
        return types.LiveConnectConfig(**kwargs)

    # ---------------------------------------------------------------- audio
    def _push_mic(self, data: bytes):
        """Se ejecuta en el loop de asyncio (via call_soon_threadsafe)."""
        if self.audio_in_queue.full():
            try:
                self.audio_in_queue.get_nowait()  # descarta lo mas viejo
            except asyncio.QueueEmpty:
                pass
        self.audio_in_queue.put_nowait(data)

    def _mic_thread(self):
        logger.info("Microfono capturando")
        last_log = 0.0
        consecutive_errors = 0
        while self.is_running:
            try:
                data = self._stream_in.read(CHUNK, exception_on_overflow=False)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.warning(f"Error temporal leyendo microfono ({consecutive_errors}): {e}")
                time.sleep(0.1)
                if consecutive_errors >= 3:
                    try:
                        logger.info("Intentando recuperar conexion con el microfono...")
                        if self._stream_in:
                            try:
                                self._stream_in.stop_stream()
                                self._stream_in.close()
                            except Exception:
                                pass
                        self._stream_in = self._pa.open(
                            format=FORMAT, channels=CHANNELS, rate=RATE_IN,
                            input=True, frames_per_buffer=CHUNK
                        )
                        consecutive_errors = 0
                        logger.info("Microfono reconectado con exito.")
                        continue
                    except Exception as re_err:
                        logger.error(f"Fallo al reconectar microfono: {re_err}")
                        time.sleep(0.5)
                        if consecutive_errors >= 12:
                            self._loop.call_soon_threadsafe(
                                self._emit, {"estado": "error", "detalle": f"microfono desconectado: {e}"})
                            break
                        continue
            rms = _rms(data)
            if rms > 250 and time.monotonic() - last_log > 1.0:
                logger.debug(f"Audio captado (volumen {rms})")
                last_log = time.monotonic()
            self._loop.call_soon_threadsafe(self._push_mic, data)

    async def _speaker_consumer(self):
        while self.is_running:
            try:
                data = await asyncio.wait_for(self.audio_out_queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                if self._playing and time.monotonic() > self._mute_until:
                    self._playing = False
                    if self._sleep_after_speech:
                        self._go_to_sleep("el asistente se despidio")  # ya se despidio
                    else:
                        self._set_estado("escuchando")
                continue
            self._playing = True
            try:
                await asyncio.to_thread(self._stream_out.write, data)
            except Exception as e:
                logger.warning(f"Error reproduciendo audio: {e}")
                try:
                    if self._stream_out:
                        try:
                            self._stream_out.stop_stream()
                            self._stream_out.close()
                        except Exception:
                            pass
                    self._stream_out = self._pa.open(
                        format=FORMAT, channels=CHANNELS, rate=RATE_OUT,
                        output=True, frames_per_buffer=CHUNK
                    )
                except Exception as re_out:
                    logger.error(f"Fallo al recuperar altavoz: {re_out}")
            self._mute_until = time.monotonic() + 0.5

    # ---------------------------------------------------------------- sesion
    def set_ptt(self, down: bool):
        """Push-to-talk: True mientras se mantiene apretada la tecla."""
        self._ptt_down = down
        if down:
            self._ptt_tail = 5  # ~320 ms extra tras soltar, para no cortar la ultima palabra

    # ---------------------------------------------------------------- modo espera / activo
    def request_wake(self):
        self._wake_requested = True

    def request_sleep(self):
        self._go_to_sleep()

    async def _activate(self, session, flush=True):
        self.mode = "activo"
        self._last_activity = time.monotonic()
        self._emit({"modo": "activo"})
        self._set_estado("escuchando")
        if self.gate:  # dejar la compuerta abierta para lo que sigue de la frase
            self.gate.open = True
            self.gate.hang = self.gate.hang_chunks
        if flush:  # mandar los ultimos segundos: "Caf, poné música" llega completo
            for chunk in list(self._preroll):
                await session.send_realtime_input(audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000"))
        self._preroll.clear()
        logger.info("Caf activado")

    def _go_to_sleep(self, motivo="despedida"):
        if not self.wake_enabled or self.mode == "dormido":
            return
        logger.info(f"Modo espera. Motivo: {motivo}")
        self.mode = "dormido"
        self._sleep_after_speech = False
        self._sleep_deadline = 0.0
        self._preroll.clear()
        if self.wake:
            self.wake.reset()
        self._emit({"modo": "dormido"})
        self._set_estado("dormido")
        logger.info("Caf en modo espera (decí 'Caf' para activarlo)")

    async def _sender(self, session):
        while self.is_running:
            if self._wake_requested:
                self._wake_requested = False
                if self.mode == "dormido":
                    await self._activate(session, flush=False)
            if not self.text_in_queue.empty():
                text = self.text_in_queue.get_nowait()
                if self.mode == "dormido":
                    await self._activate(session, flush=False)
                await session.send_realtime_input(text=text)
                self._last_activity = time.monotonic()
                self._emit({"transcripcion": {"rol": "usuario", "texto": text}})
                continue
            try:
                data = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if self.muted:
                continue
            if self.wake_enabled:
                now = time.monotonic()
                if self.mode == "dormido":
                    self._preroll.append(data)
                    if await asyncio.to_thread(self.wake.feed, data):
                        await self._activate(session)
                    continue
                if self._sleep_deadline and now > self._sleep_deadline:
                    self._go_to_sleep("la despedida no llego a sonar a tiempo")
                    continue
                if now - self._last_activity > self.idle_seconds and not self._playing:
                    self._go_to_sleep(f"{self.idle_seconds:.0f}s sin actividad")
                    continue
            if not self.headphones and not self._ptt_down and (self._playing or time.monotonic() < self._mute_until):
                continue  # evita eco: no mandar el mic mientras suena Caf

            flush = False
            if self.ptt_enabled:
                if self._ptt_down:
                    chunks = [data]
                elif self._ptt_tail > 0:
                    self._ptt_tail -= 1
                    chunks = [data]
                    flush = self._ptt_tail == 0
                else:
                    chunks = []
            elif self.gate:
                was_open = self.gate.open
                chunks = self.gate.process(data)
                if self.gate.open:
                    self._last_activity = time.monotonic()
                if self.gate.open != was_open:
                    logger.debug(f"gate {'ABIERTA' if self.gate.open else 'cerrada'} "
                                 f"(rms={self.gate.last_rms}, umbral={self.gate.threshold:.0f})")
                if time.monotonic() - self._last_gate_log > 2.0:
                    self._last_gate_log = time.monotonic()
                    logger.debug(f"gate: rms={self.gate.last_rms} piso={self.gate.floor:.0f} "
                                 f"umbral={self.gate.threshold:.0f} abierta={self.gate.open}")
            else:
                chunks = [data]

            for c in chunks:
                await session.send_realtime_input(audio=types.Blob(data=c, mime_type="audio/pcm;rate=16000"))
            if flush:
                await session.send_realtime_input(audio_stream_end=True)

    async def _receiver(self, session):
        # receive() termina al completarse cada turno del modelo: hay que llamarlo en bucle.
        while self.is_running:
            got_any = False
            async for response in session.receive():
                got_any = True
                await self._on_message(response, session)
            if not got_any:
                await asyncio.sleep(0.05)

    async def _on_message(self, response, session):
        sc = response.server_content
        if sc is not None:
            if sc.interrupted:
                while not self.audio_out_queue.empty():
                    self.audio_out_queue.get_nowait()
                self._mute_until = 0.0
                self._set_estado("escuchando")
            if sc.model_turn:
                for part in sc.model_turn.parts or []:
                    if part.inline_data and part.inline_data.data:
                        self._last_activity = time.monotonic()
                        self.audio_out_queue.put_nowait(part.inline_data.data)
                        self._set_estado("hablando")
            if sc.input_transcription and sc.input_transcription.text:
                self._last_activity = time.monotonic()
                self._emit({"transcripcion": {"rol": "usuario", "texto": sc.input_transcription.text}})
            if sc.output_transcription and sc.output_transcription.text:
                self._emit({"transcripcion": {"rol": "caf", "texto": sc.output_transcription.text}})
        if response.tool_call:
            for fc in response.tool_call.function_calls or []:
                asyncio.create_task(self._run_tool(fc, session))
        upd = response.session_resumption_update
        if upd and upd.resumable and upd.new_handle:
            self._resume_handle = upd.new_handle
        if response.go_away:
            raise ConnectionError(f"El servidor pidio cerrar la sesion (go_away): {response.go_away}")

    async def _run_tool(self, fc, session):
        logger.info(f"Tool solicitada: {fc.name} {fc.args}")
        self._set_estado("ejecutando_herramienta", fc.name)
        spec = TOOLS.get(fc.name)
        try:
            if not spec:
                res = f"Herramienta desconocida: {fc.name}"
            elif fc.name == "desactivar_asistente":
                if self.wake_enabled:
                    self._sleep_after_speech = True
                    self._sleep_deadline = time.monotonic() + 8  # por si no llega a decir nada
                    res = "Listo, entrando en modo espera. Despedite con una frase muy corta."
                else:
                    res = "El modo espera no está disponible en esta sesión."
            else:
                args = {k: v for k, v in (fc.args or {}).items() if k in spec["params"]}
                res = await asyncio.wait_for(asyncio.to_thread(spec["fn"], **args), timeout=TOOL_TIMEOUT)
        except asyncio.TimeoutError:
            res = f"Error: la herramienta {fc.name} tardo mas de {TOOL_TIMEOUT}s."
        except Exception as e:
            res = f"Error interno en herramienta: {e}"
        logger.info(f"Tool resuelta: {res}")
        self._emit({"herramienta": {"nombre": fc.name, "resultado": res}})
        try:
            await session.send_tool_response(function_responses=[
                types.FunctionResponse(id=fc.id, name=fc.name, response={"result": res})])
        except Exception as e:
            logger.error(f"No se pudo enviar la respuesta de la tool: {e}")

    def _setup_wake_key(self):
        """Tecla de respaldo para despertarlo sin decir 'Caf' (por defecto F8)."""
        if not self.wake_enabled:
            return
        key = os.getenv("CAF_WAKE_KEY", "f8")
        try:
            import keyboard
            self._ptt_hooks.append(keyboard.on_press_key(key, lambda e: self.request_wake()))
            logger.info(f"Tecla para despertar a Caf: '{key}'")
        except Exception as ex:
            logger.warning(f"No se pudo registrar la tecla de despertar ({ex})")

    def _setup_ptt(self):
        if not self.ptt_enabled:
            return
        key = os.getenv("CAF_PTT_KEY", "f9")
        try:
            import keyboard
            self._ptt_hooks = [
                keyboard.on_press_key(key, lambda e: self.set_ptt(True)),
                keyboard.on_release_key(key, lambda e: self.set_ptt(False)),
            ]
            logger.info(f"Push-to-talk activo: mantene apretada la tecla '{key}' para hablar")
        except Exception as e:
            self.ptt_enabled = False
            logger.warning(f"No se pudo activar push-to-talk ({e}). Instala: pip install keyboard")

    # ---------------------------------------------------------------- ciclo de vida
    async def start(self):
        self.is_running = True
        self._loop = asyncio.get_running_loop()
        bg = []
        try:
            if self.use_audio_hardware:
                try:
                    self._pa = pyaudio.PyAudio()
                    self._stream_in = self._pa.open(format=FORMAT, channels=CHANNELS, rate=RATE_IN,
                                                    input=True, frames_per_buffer=CHUNK)
                    self._stream_out = self._pa.open(format=FORMAT, channels=CHANNELS, rate=RATE_OUT,
                                                     output=True, frames_per_buffer=CHUNK)
                except Exception as e:
                    self._emit({"estado": "error", "detalle": f"audio: {e}"})
                    raise RuntimeError(f"No se pudo abrir el audio: {e}") from e
                bg.append(asyncio.create_task(asyncio.to_thread(self._mic_thread)))
                bg.append(asyncio.create_task(self._speaker_consumer()))

            self._setup_ptt()
            self._setup_wake_key()

            attempt = 0
            while self.is_running:
                connected_at = time.monotonic()
                try:
                    self._set_estado("reconectando" if attempt else "conectando", MODEL)
                    async with self.client.aio.live.connect(model=MODEL, config=self._build_config()) as session:
                        logger.info(f"Conectado a {MODEL}")
                        while not self.audio_in_queue.empty():  # audio viejo de antes de conectar
                            self.audio_in_queue.get_nowait()
                        self._set_estado("escuchando" if self.mode == "activo" else "dormido")
                        self._emit({"modo": self.mode})
                        tasks = [asyncio.create_task(self._sender(session)),
                                 asyncio.create_task(self._receiver(session))]
                        try:
                            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                            for t in done:
                                t.result()  # re-lanza el error que corto la sesion
                        finally:
                            # Siempre cancelar y recoger las tareas hijas (tambien con Ctrl+C),
                            # asi no quedan excepciones "never retrieved".
                            for t in tasks:
                                t.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception("Error en la sesion Live")
                    if ("quota" in str(e).lower() or "1011" in str(e)) and os.getenv("CAF_SEARCH", "0") == "1":
                        logger.warning("Fallo de cuota en Google Search grounding. Desactivando CAF_SEARCH y reintentando...")
                        os.environ["CAF_SEARCH"] = "0"
                        continue
                    self._emit({"estado": "error", "detalle": str(e)})
                    attempt = 1 if time.monotonic() - connected_at > 10 else attempt + 1
                    if attempt >= 3:
                        self._resume_handle = None  # por si el handle quedo invalido
                    await asyncio.sleep(min(2 ** attempt, 30))
        finally:
            self.is_running = False
            for t in bg[1:]:
                t.cancel()  # consumidor de parlantes
            if bg:  # el hilo del mic termina solo (is_running=False); esperarlo antes de cerrar el stream
                try:
                    await asyncio.wait_for(asyncio.shield(bg[0]), timeout=2)
                except Exception:
                    pass
            try:
                import keyboard
                for h in self._ptt_hooks:
                    keyboard.unhook(h)
            except Exception:
                pass
            for s in (self._stream_in, self._stream_out):
                try:
                    if s:
                        s.stop_stream()
                        s.close()
                except Exception:
                    pass
            if self._pa:
                self._pa.terminate()

    def stop(self):
        self.is_running = False
