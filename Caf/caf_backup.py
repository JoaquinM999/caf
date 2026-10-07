import sys
import os
import time
import asyncio
import tempfile
import speech_recognition as sr
import pygame
import edge_tts
import threading
import re
import winsound
import json
import pyaudio
from vosk import Model, KaldiRecognizer

# Evitar buffering de salida y forzar UTF-8 para que Rust no cierre el pipe
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stdin.reconfigure(encoding='utf-8')
pygame.mixer.init()

is_busy = False

def clean_text(text):
    # Limpiar markdown y símbolos molestos que arruinan el TTS
    text = re.sub(r'[*#_~`\[\]]', '', text)
    text = re.sub(r'http[s]?://\S+', 'un enlace', text)
    text = text.replace('^', '')
    return text.strip()

async def generar_audio(texto, ruta_archivo):
    texto = clean_text(texto)
    if not texto:
        return False
    communicate = edge_tts.Communicate(texto, "es-AR-TomasNeural")
    await communicate.save(ruta_archivo)
    return True

def reproducir_audio(ruta_archivo):
    try:
        pygame.mixer.music.load(ruta_archivo)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()
    except Exception:
        pass

def play_text(texto):
    global is_busy
    is_busy = True
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        if asyncio.run(generar_audio(texto, temp_path)):
            reproducir_audio(temp_path)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
    finally:
        is_busy = False

import io
import wave
import math
import struct

def play_tone(freq, duration=0.2, volume=0.3):
    # Genera un tono limpio con decaimiento
    num_samples = int(44100 * duration)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        for i in range(num_samples):
            # Envolvente exponencial para que no suene brusco
            env = math.exp(-i / (num_samples / 3))
            sample = volume * env * math.sin(2 * math.pi * freq * (i / 44100.0))
            wf.writeframes(struct.pack('<h', int(sample * 32767.0)))
    buf.seek(0)
    try:
        sound = pygame.mixer.Sound(buf)
        sound.play()
    except:
        pass

def escuchar(auto_reply=False):
    global is_busy
    is_busy = True
    try:
        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 2.0 # Permite 2 segundos de silencio mientras piensas qué decir sin cortar
        with sr.Microphone() as source:
            print("VOICE_STATUS:Ajustando", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            print("VOICE_STATUS:Escuchando", flush=True)
            # Un tono suave para indicar que empezó a escuchar
            if not auto_reply:
                play_tone(600, 0.2)
                
            try:
                # timeout controla cuánto espera en silencio antes de rendirse
                t = 4 if auto_reply else 10 # timeout global de 10s si no hablas
                # timeout (límite de silencio inicial), phrase_time_limit (límite máximo de 15 segundos)
                audio = recognizer.listen(source, timeout=t, phrase_time_limit=15)
                
                print("VOICE_STATUS:Procesando", flush=True)
                
                import tempfile
                audio_file = os.path.join(tempfile.gettempdir(), "coucou_voice.wav")
                with open(audio_file, "wb") as f:
                    f.write(audio.get_wav_data())
                
                print(f"VOICE_AUDIO_IN:{audio_file}", flush=True)
                
                # Tono de confirmación exitosa
                play_tone(800, 0.15)
                # ¡CRÍTICO! Resetear a inactivo para que la interfaz se borre
                print("VOICE_STATUS:Inactivo", flush=True)
            except sr.WaitTimeoutError:
                print("VOICE_STATUS:Inactivo", flush=True)
            except Exception:
                play_tone(300, 0.3) # Tono grave de error
                print("VOICE_STATUS:Error", flush=True)
    finally:
        is_busy = False

def wake_word_listener():
    model_path = os.path.join(os.path.dirname(__file__), "modelo_vosk")
    # Redirigir el stderr de Vosk que es muy ruidoso
    from vosk import SetLogLevel
    SetLogLevel(-1)
    
    # Esperar hasta que el modelo exista para no crashear
    while not os.path.exists(model_path):
        time.sleep(2)
        
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
    stream.start_stream()

    wake_words = ["caf", "cap", "caz", "gap", "kaf", "kav", "caff", "cif", "gas", "cat", "calf", "cafe", "café", "cash", "cruz", "craft", "chat", "cau", "chau", "sat"]

    while True:
        if is_busy:
            if stream.is_active():
                stream.stop_stream()
            time.sleep(0.1)
            continue
        else:
            if not stream.is_active():
                stream.start_stream()
            
        data = stream.read(4000, exception_on_overflow=False)
        if len(data) == 0:
            continue
            
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
        else:
            result = json.loads(rec.PartialResult())
            text = result.get("partial", "")
            
        if text:
            # Imprimir en consola para que veas qué está entendiendo Vosk
            print(f"VOSK (Debug): {text}", file=sys.stderr, flush=True)

        # Comprobar si la palabra está sola para no disparar por error con palabras que la contienen
        palabras = text.split()
        if any(w in palabras for w in wake_words):
            escuchar()
            rec.Reset()

def main():
    t = threading.Thread(target=wake_word_listener, daemon=True)
    t.start()
    
    print("VOICE_STATUS:Inactivo", flush=True)
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line.startswith("VOICE_OUT:"):
            texto = line[len("VOICE_OUT:"):]
            print("VOICE_STATUS:Hablando", flush=True)
            play_text(texto)
            print("VOICE_STATUS:Inactivo", flush=True)
            # Luego de hablar, se queda escuchando automáticamente para seguir la conversación
            escuchar(auto_reply=True)
        elif line == "WAKE_UP":
            escuchar()

if __name__ == "__main__":
    main()
