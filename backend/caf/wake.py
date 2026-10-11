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

# Variantes que Vosk devolvia para "Caf" en la version anterior (afinadas con uso real). Se pueden cambiar con CAF_WAKE_WORDS.
DEFAULT_WORDS = ("caf,cap,caz,gap,kaf,kav,caff,cif,gas,cat,calf,cafe,café,cash,cruz,craft,chat,cau,chau,sat")


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
    def __init__(self, model_path, words=None, sample_rate=16000, max_words=5, cooldown=1.5):
        from vosk import KaldiRecognizer, Model, SetLogLevel
        SetLogLevel(-1)
        self.words = {w.strip().lower() for w in (words or os.getenv("CAF_WAKE_WORDS", DEFAULT_WORDS)).split(",") if w.strip()}
        self.max_words = max_words
        self.cooldown = cooldown
        self._last = 0.0
        self.rec = KaldiRecognizer(Model(str(model_path)), sample_rate)
        logger.info(f"Palabra de activacion lista (variantes: {sorted(self.words)})")

    def matches(self, text: str) -> bool:
        """'caf', 'hola caf', 'che caf, poné música' -> si. Una frase larga donde 'cap' aparece al pasar -> no."""
        tokens = text.lower().split()
        if not tokens:
            return False
        return any(t in self.words for t in tokens[:3]) and len(tokens) <= self.max_words + 3

    def feed(self, data: bytes) -> bool:
        if time.monotonic() - self._last < self.cooldown:
            return False
        if self.rec.AcceptWaveform(data):
            text = json.loads(self.rec.Result()).get("text", "")
        else:
            text = json.loads(self.rec.PartialResult()).get("partial", "")
        if text:
            logger.debug(f"wake: oigo '{text}'")
        if self.matches(text):
            self.rec.Reset()
            self._last = time.monotonic()
            return True
        return False

    def reset(self):
        self.rec.Reset()
