import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

def get_stats_path() -> Path:
    ws = Path.home() / "CafWorkspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws / "estadisticas.json"

DEFAULT_STATS = {
    "total_conversations": 0,
    "total_user_words": 0,
    "total_caf_words": 0,
    "total_seconds_talked": 0,
    "tools_used": {
        "spotify": 0,
        "buscar_web": 0,
        "preparar_email": 0,
        "recordar": 0,
        "coucou_pills": 0,
        "abrir_programa": 0,
        "otros": 0
    },
    "daily": {},
    "history": []
}

def load_stats() -> dict:
    p = get_stats_path()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_STATS.items():
                    if k not in data:
                        data[k] = v
                if "tools_used" in data:
                    for tk, tv in DEFAULT_STATS["tools_used"].items():
                        if tk not in data["tools_used"]:
                            data["tools_used"][tk] = tv
                return data
        except Exception as e:
            logger.warning(f"Error cargando estadisticas: {e}")
    return json.loads(json.dumps(DEFAULT_STATS))

def save_stats(stats: dict):
    p = get_stats_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Error guardando estadisticas: {e}")

def record_turn(user_text: str = "", caf_text: str = "", duration_seconds: float = 0):
    try:
        stats = load_stats()
        stats["total_conversations"] += 1
        u_words = len(user_text.split()) if user_text else 0
        c_words = len(caf_text.split()) if caf_text else 0
        stats["total_user_words"] += u_words
        stats["total_caf_words"] += c_words
        stats["total_seconds_talked"] += max(1, int(duration_seconds))
        
        today = datetime.now().strftime("%Y-%m-%d")
        daily = stats.setdefault("daily", {})
        daily[today] = daily.get(today, 0) + (u_words + c_words)

        stats.setdefault("history", []).append({
            "timestamp": datetime.now().isoformat(),
            "date": today,
            "user_words": u_words,
            "caf_words": c_words
        })
        if len(stats["history"]) > 200:
            stats["history"] = stats["history"][-200:]
        save_stats(stats)
    except Exception as e:
        logger.warning(f"Error registrando turno de estadistica: {e}")

def record_tool_call(tool_name: str):
    try:
        stats = load_stats()
        tools = stats.setdefault("tools_used", {})
        category = "otros"
        low = tool_name.lower()
        if "spotify" in low:
            category = "spotify"
        elif "buscar" in low or "leer_pagina" in low:
            category = "buscar_web"
        elif "email" in low or "correo" in low:
            category = "preparar_email"
        elif "recordar" in low or "memoria" in low or "olvidar" in low:
            category = "recordar"
        elif "pills" in low or "coucou" in low:
            category = "coucou_pills"
        elif "programa" in low:
            category = "abrir_programa"
        tools[category] = tools.get(category, 0) + 1
        save_stats(stats)
    except Exception as e:
        logger.warning(f"Error registrando herramienta en estadisticas: {e}")
