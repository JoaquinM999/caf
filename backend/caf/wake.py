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

# Variantes auténticas de activación exclusiva para Caf.
# NUNCA agregar palabras comunes o fragmentos monosilábicos sueltos para evitar falsos positivos.
DEFAULT_WORDS = "caf,cafe,café,cafecito,caff,caffe,kaf,kafe,coffee"


def _is_valid_model(p: Path) -> bool:
    return p.exists() and (p / "am" / "final.mdl").exists() and (p / "conf" / "model.conf").exists()


def find_model_path():
    import sys
    env = os.getenv("CAF_VOSK_MODEL")
    if env and _is_valid_model(Path(env)):
        return Path(env).resolve()

    candidates = []

    # Check near executable (for frozen PyInstaller bundle or direct binary)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for base in (exe_dir, exe_dir.parent, exe_dir.parent.parent):
            for rel in ("modelo_vosk", "Caf/modelo_vosk", "binaries/modelo_vosk", "resources/modelo_vosk"):
                candidates.append(base / rel)

    # Check cwd and parents
    cwd = Path.cwd().resolve()
    for base in (cwd, cwd.parent, cwd.parent.parent):
        for rel in ("modelo_vosk", "Caf/modelo_vosk", "model", "binaries/modelo_vosk"):
            candidates.append(base / rel)

    # Check module location if not frozen
    if not getattr(sys, "frozen", False):
        here = Path(__file__).resolve()
        for base in (here.parents[1], here.parents[2] if len(here.parents) > 2 else here.parent):
            for rel in ("modelo_vosk", "Caf/modelo_vosk", "model", "vosk-model-small-es"):
                candidates.append(base / rel)

    # Standard user / local app data locations
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Coucou" / "modelo_vosk")
        candidates.append(Path(local_app_data) / "Coucou" / "resources" / "modelo_vosk")

    candidates.append(Path.home() / "OneDrive" / "Escritorio" / "Coucou" / "Caf" / "modelo_vosk")

    for cand in candidates:
        try:
            if _is_valid_model(cand):
                return cand.resolve()
        except Exception:
            continue

    return None


class WakeWord:
    def __init__(self, model_path, words=None, sample_rate=16000, cooldown=1.2):
        from vosk import KaldiRecognizer, Model, SetLogLevel
        logger.info(f"Inicializando modelo de activacion Vosk desde: {model_path}")
        SetLogLevel(-1)
        self.words = {w.strip().lower() for w in (words or os.getenv("CAF_WAKE_WORDS", DEFAULT_WORDS)).split(",") if w.strip()}
        self.cooldown = cooldown
        self._last = 0.0

        # Usar el reconocedor con el modelo en español.
        self.rec = KaldiRecognizer(Model(str(model_path)), sample_rate)
        logger.info(f"Palabra de activacion lista (exclusivo 'Caf', variantes: {sorted(self.words)})")

    def matches(self, text: str) -> bool:
        """Determina si el texto transcrito contiene la palabra de activación 'Caf'."""
        if not text:
            return False
        tokens = [t.strip(",.?!¡¿\"'").lower() for t in text.split()]
        if not tokens:
            return False

        indices = [i for i, t in enumerate(tokens) if t in self.words]
        if indices:
            # Si es una frase corta (hasta 4 palabras, ej: 'caf', 'hola caf', 'che caf'):
            if len(tokens) <= 4:
                return True
            # En frases más largas, debe estar al inicio (primeras 2 palabras)
            return any(i <= 1 for i in indices)

        # Variantes fonéticas comunes en español si empieza con vocativo
        # Ej: "che cap", "hola cap", "che caz"
        if len(tokens) >= 2 and tokens[0] in ("che", "hola", "oye", "ey", "buen", "buenas") and tokens[1] in ("cap", "caz", "caf", "caff", "kaf"):
            return True

        return False

    def feed(self, data: bytes) -> bool:
        """Procesa un chunk de audio PCM. Devuelve True inmediatamente si detecta 'Caf'."""
        if time.monotonic() - self._last < self.cooldown:
            return False

        if self.rec.AcceptWaveform(data):
            text = json.loads(self.rec.Result()).get("text", "")
            if text and self.matches(text):
                logger.info(f"¡Activación confirmada por frase completa! ('{text}') -> Despertando a Caf")
                self.rec.Reset()
                self._last = time.monotonic()
                return True
        else:
            # Detección instantánea en tiempo real sin esperar pausas ni silencios
            partial = json.loads(self.rec.PartialResult()).get("partial", "")
            if partial and self.matches(partial):
                logger.info(f"¡Activación instantánea confirmada! ('{partial}') -> Despertando a Caf")
                self.rec.Reset()
                self._last = time.monotonic()
                return True
        return False

    def reset(self):
        self.rec.Reset()


