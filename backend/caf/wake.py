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
# NUNCA agregar palabras comunes o fragmentos monosilábicos (cap, caz, chef, gap, cif) porque
# causan falsos positivos inmediatos al hablar en español cotidiano con otras personas en la habitación.
DEFAULT_WORDS = "caf,cafe,cafecito,coffee"


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
        self._partial_hits = 0

        # Gramática enfocada: permite únicamente las palabras reales de Caf y vocativos naturales ("hola", "che", "ey", "oye"),
        # absorbiendo todo el resto del idioma en [unk].
        vocab_wake = {"caf", "cafe", "cafecito", "coffee"}
        grammar_list = sorted(vocab_wake | {"hola", "che", "ey", "oye", "[unk]"})
        try:
            self.rec = KaldiRecognizer(Model(str(model_path)), sample_rate, json.dumps(grammar_list))
            logger.info(f"Palabra de activacion lista con gramatica enfocada (variantes: {sorted(self.words)})")
        except Exception as e:
            logger.warning(f"No se pudo inicializar con gramática ({e}), usando reconocedor abierto.")
            self.rec = KaldiRecognizer(Model(str(model_path)), sample_rate)
            logger.info(f"Palabra de activacion lista (variantes: {sorted(self.words)})")

    def matches(self, text: str) -> bool:
        """Verifica si el texto reconocido contiene la palabra de activación de Caf."""
        tokens = [t for t in text.lower().split() if t != "[unk]"]
        if not tokens:
            return False
        # Obligatorio: debe contener una de las variantes reales de Caf
        return any(t in self.words for t in tokens)

    def feed(self, data: bytes) -> bool:
        if time.monotonic() - self._last < self.cooldown:
            return False

        if self.rec.AcceptWaveform(data):
            text = json.loads(self.rec.Result()).get("text", "")
            tokens = [t for t in text.lower().split() if t != "[unk]"]
            if tokens and self.matches(" ".join(tokens)):
                logger.info(f"¡Activación por voz confirmada! ('{' '.join(tokens)}') -> Despertando a Caf")
                self.rec.Reset()
                self._last = time.monotonic()
                return True
        return False

    def reset(self):
        self.rec.Reset()

