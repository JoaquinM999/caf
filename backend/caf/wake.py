"""Palabra de activacion local ("Caf") con Vosk.

En modo dormido el audio NO sale de la PC: se analiza aca con un modelo chico en
espanol. Vosk a veces entiende mal "Caf" (cap, kaf, cafe...), por eso se aceptan variantes.
"""
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Variantes auténticas de activación para Caf.
# NUNCA agregar palabras comunes o fragmentos monosilábicos (cap, caz, chef, gap, cif, gas, cat, caso, campo)
# porque causan falsos positivos inmediatos al hablar en español cotidiano con otras personas.
DEFAULT_WORDS = "caf,cafe,café,cafecito,coffee,coucou,caff,caffe,coffe"


def find_model_path():
    import sys
    env = os.getenv("CAF_VOSK_MODEL")
    if env and Path(env).exists():
        return Path(env)
    # Check near executable (for frozen PyInstaller bundle)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for rel in ("modelo_vosk", "Caf/modelo_vosk", "model", "resources/modelo_vosk"):
            if (exe_dir / rel).exists():
                return exe_dir / rel
    # Check cwd
    for rel in ("modelo_vosk", "Caf/modelo_vosk", "model"):
        if (Path.cwd() / rel).exists():
            return Path.cwd() / rel
    here = Path(__file__).resolve()
    for base in (here.parents[1], here.parents[2], here.parents[3] if len(here.parents) > 3 else here.parents[2]):
        for rel in ("modelo_vosk", "Caf/modelo_vosk", "model", "vosk-model-small-es"):
            if (base / rel).exists():
                return base / rel
    return None


class WakeWord:
    def __init__(self, model_path, words=None, sample_rate=16000, cooldown=1.5):
        from vosk import KaldiRecognizer, Model, SetLogLevel
        SetLogLevel(-1)
        self.words = {w.strip().lower() for w in (words or os.getenv("CAF_WAKE_WORDS", DEFAULT_WORDS)).split(",") if w.strip()}
        self.cooldown = cooldown
        self._last = 0.0

        # Usar el reconocedor abierto con el modelo completo en español.
        # NUNCA restringir a una lista pequeña de palabras (gramática fija) porque Kaldi fuerza
        # cualquier ruido, tos, susurro o palabra ajena (ej. "casa", "capaz", "qué tal") a colapsar
        # en "café", provocando un bucle interminable de encendido y apagado con cualquier sonido.
        self.rec = KaldiRecognizer(Model(str(model_path)), sample_rate)
        logger.info(f"Palabra de activacion lista con modelo abierto (variantes: {sorted(self.words)})")

    def matches(self, text: str) -> bool:
        """'caf', 'hola caf', 'che caf, poné música' -> si. Frases largas casuales sin vocativo al inicio -> no."""
        tokens = [t.strip(",.?!¡¿").lower() for t in text.split()]
        if not tokens:
            return False

        indices = [i for i, t in enumerate(tokens) if t in self.words]
        if not indices:
            return False

        # Si es una frase corta (hasta 4 palabras, ej: 'caf', 'hola caf', 'caf pone musica', 'che caf'):
        if len(tokens) <= 4:
            return True

        # Si es una frase más larga, la palabra de activación debe estar al inicio (primeras 2 palabras)
        return any(i <= 1 for i in indices)

    def feed(self, data: bytes) -> bool:
        if time.monotonic() - self._last < self.cooldown:
            return False

        if self.rec.AcceptWaveform(data):
            text = json.loads(self.rec.Result()).get("text", "")
            if text and self.matches(text):
                logger.info(f"¡Activación por voz confirmada! ('{text}') -> Despertando a Caf")
                self.rec.Reset()
                self._last = time.monotonic()
                return True
        return False

    def reset(self):
        self.rec.Reset()

