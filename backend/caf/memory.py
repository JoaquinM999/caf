"""Sistema de memoria persistente para Caf.

Guarda preferencias, instrucciones del usuario y datos importantes en CafWorkspace/memoria.json
para que persistan entre reinicios y sesiones.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path.home() / "CafWorkspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_FILE = WORKSPACE_DIR / "memoria.json"

DEFAULT_MEMORIES = [
    "Cada vez que el usuario pida el último video de alguien, se refiere siempre al video más recientemente subido (por fecha de subida).",
]


def _init_memory_file():
    if not MEMORY_FILE.exists():
        data = {
            "recuerdos": list(DEFAULT_MEMORIES)
        }
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"No se pudo crear {MEMORY_FILE}: {e}")


def cargar_recuerdos() -> list[str]:
    """Carga la lista de recuerdos e instrucciones guardadas."""
    _init_memory_file()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            recuerdos = data.get("recuerdos", [])
            if not isinstance(recuerdos, list):
                recuerdos = []
            return recuerdos
    except Exception as e:
        logger.warning(f"Error al leer {MEMORY_FILE}: {e}")
        return list(DEFAULT_MEMORIES)


def guardar_recuerdo(recuerdo: str) -> str:
    """Guarda un nuevo recuerdo o instrucción en la memoria persistente."""
    recuerdo = (recuerdo or "").strip()
    if not recuerdo:
        return "Error: no se especificó qué recordar."
    recuerdos = cargar_recuerdos()
    # Evitar duplicados exactos
    if recuerdo in recuerdos:
        return f"Ya tenía anotado en mi memoria: '{recuerdo}'."
    recuerdos.append(recuerdo)
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"recuerdos": recuerdos}, f, ensure_ascii=False, indent=2)
        return f"Entendido, guardado en mi memoria para siempre: '{recuerdo}'."
    except Exception as e:
        return f"Error al guardar en memoria: {e}"


def olvidar_recuerdo(recuerdo: str) -> str:
    """Elimina un recuerdo o instrucción de la memoria persistente."""
    recuerdo = (recuerdo or "").strip().lower()
    if not recuerdo:
        return "Error: no se especificó qué olvidar."
    recuerdos = cargar_recuerdos()
    nuevos = [r for r in recuerdos if recuerdo not in r.lower()]
    if len(nuevos) == len(recuerdos):
        return f"No encontré en mi memoria nada relacionado con '{recuerdo}'."
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"recuerdos": nuevos}, f, ensure_ascii=False, indent=2)
        return f"Listo, olvidé todo lo relacionado con '{recuerdo}' de mi memoria."
    except Exception as e:
        return f"Error al actualizar memoria: {e}"


def listar_recuerdos() -> str:
    """Devuelve un resumen de todo lo que Caf recuerda del usuario."""
    recuerdos = cargar_recuerdos()
    if not recuerdos:
        return "Actualmente mi memoria está vacía."
    lineas = [f"- {r}" for r in recuerdos]
    return "Esto es lo que tengo guardado en mi memoria:\n" + "\n".join(lineas)


def obtener_prompt_memoria() -> str:
    """Devuelve la sección de memoria para inyectar en el system prompt."""
    recuerdos = cargar_recuerdos()
    if not recuerdos:
        return ""
    items = "\n".join(f"- {r}" for r in recuerdos)
    return f"""

MEMORIA Y PREFERENCIAS RECORDADAS DEL USUARIO (instrucciones que te pidió recordar):
{items}
Cumplí siempre con estas preferencias y recuerdos cuando interactúes o ejecutes acciones."""
