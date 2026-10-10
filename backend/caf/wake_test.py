"""Calibrar la palabra de activacion: python -m caf.wake_test

Decí "Caf" unas 8 veces, de a una y con pausas. Muestra que palabra entiende Vosk
cada vez y te sugiere la variable CAF_WAKE_WORDS.
"""
import collections
import json
import time

import pyaudio
from vosk import KaldiRecognizer, Model, SetLogLevel

from caf.wake import DEFAULT_WORDS, find_model_path


def main():
    path = find_model_path()
    if not path:
        print("No encontré la carpeta modelo_vosk. Definí CAF_VOSK_MODEL con su ruta.")
        return
    SetLogLevel(-1)
    rec = KaldiRecognizer(Model(str(path)), 16000)
    pa = pyaudio.PyAudio()
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
    print("Decí 'Caf' unas 8 veces, de a una, con pausas. Dura 30 segundos...\n")
    solas = collections.Counter()
    t0 = time.time()
    while time.time() - t0 < 30:
        data = stream.read(4000, exception_on_overflow=False)
        if rec.AcceptWaveform(data):
            texto = json.loads(rec.Result()).get("text", "").strip()
            if texto:
                print("  entendí:", texto)
                if len(texto.split()) == 1:
                    solas[texto] += 1
    stream.stop_stream(); stream.close(); pa.terminate()
    if not solas:
        print("\nNo entendí ninguna palabra suelta. Revisá el micrófono y el volumen.")
        return
    palabras = sorted(set(DEFAULT_WORDS.split(",")) | set(solas))
    print("\nPalabras sueltas que oyó:", dict(solas))
    print("\nProbá con:")
    print(f'  $env:CAF_WAKE_WORDS="{",".join(palabras)}"')


if __name__ == "__main__":
    main()
