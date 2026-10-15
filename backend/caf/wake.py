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

# Variantes fonéticas reales que Vosk devuelve para "Caf" en español.
# Se eliminaron palabras comunes del español (campo, caso, car, chat, chau, gas, etc.) que causaban falsos positivos.
DEFAULT_WORDS = (
    "caf,cap,kaf,kav,caff,cif,calf,cafe,café,caffe,coffe,coffee,cafecito,coucou,cucu,kuku,chef,kef,kuf,cuf,caz,gap"
)


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
        # Gramática enfocada: restringe el decodificador acústico a las variantes de activación y saludos
        # presentes en el vocabulario de Vosk, enviando cualquier otra palabra del español a [unk].
        # Esto aumenta drásticamente la sensibilidad hacia "Caf" y reduce los falsos positivos a cero.
        vocab_wake = {"caf", "cap", "cafe", "coffee", "cafecito", "chef", "caz", "gap", "cif"}
        grammar_list = sorted(vocab_wake | {"hola", "che", "ey", "oye", "bueno", "mochi", "[unk]"})
        try:
            self.rec = KaldiRecognizer(Model(str(model_path)), sample_rate, json.dumps(grammar_list))
            logger.info(f"Palabra de activacion lista con gramatica enfocada (variantes: {sorted(self.words)})")
        except Exception as e:
            logger.warning(f"No se pudo inicializar con gramática ({e}), usando reconocedor abierto.")
            self.rec = KaldiRecognizer(Model(str(model_path)), sample_rate)
            logger.info(f"Palabra de activacion lista (variantes: {sorted(self.words)})")

    def matches(self, text: str) -> bool:
        """'caf', 'hola caf', 'che caf, poné música' -> si. Frases sin palabra clave -> no."""
        tokens = [t for t in text.lower().split() if t != "[unk]"]
        if not tokens:
            return False
        # Si contiene alguna de las palabras de activación
        if any(t in self.words for t in tokens):
            # Para frases de hasta 5 palabras, es activación segura
            if len(tokens) <= 5:
                return True
            # Para frases más largas, debe estar en las primeras 3 palabras
            # o acompañada de un saludo/llamado ("hola", "che", "ey", "oye", "bueno")
            if any(t in self.words for t in tokens[:3]):
                return True
            saludos = {"hola", "che", "ey", "oye", "bueno"}
            for i, t in enumerate(tokens):
                if t in self.words and i > 0 and tokens[i - 1] in saludos:
                    return True
        return False

    def feed(self, data: bytes) -> bool:
        if time.monotonic() - self._last < self.cooldown:
            return False
        is_final = self.rec.AcceptWaveform(data)
        if is_final:
            text = json.loads(self.rec.Result()).get("text", "")
        else:
            text = json.loads(self.rec.PartialResult()).get("partial", "")
        if text:
            tokens = [t for t in text.lower().split() if t != "[unk]"]
            if tokens:
                clean_text = " ".join(tokens)
                logger.info(f"Vosk escuchó ({'final' if is_final else 'parcial'}): '{clean_text}'")
                if self.matches(clean_text):
                    logger.info(f"¡Activación por voz detectada! ('{clean_text}') -> Despertando a Caf")
                    self.rec.Reset()
                    self._last = time.monotonic()
                    return True
        return False

    def reset(self):
        self.rec.Reset()

