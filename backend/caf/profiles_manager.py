import os
import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import List

class Profile(BaseModel):
    nombre: str
    voz: str
    herramientas: List[str]
    system_instruction: str

def _get_profiles_dir() -> Path:
    import sys
    d = Path(__file__).parent / "profiles"
    if d.exists():
        return d
    if getattr(sys, "frozen", False):
        meipass_d = Path(getattr(sys, "_MEIPASS", "")) / "caf" / "profiles"
        if meipass_d.exists():
            return meipass_d
        exe_d = Path(sys.executable).parent / "profiles"
        if exe_d.exists():
            return exe_d
    for candidate in (Path.cwd() / "backend" / "caf" / "profiles", Path.cwd() / "profiles"):
        if candidate.exists():
            return candidate
    return d


def load_profile(profile_name: str) -> Profile:
    profiles_dir = _get_profiles_dir()
    profile_path = profiles_dir / f"{profile_name}.yaml"
    
    if not profile_path.exists():
        raise FileNotFoundError(f"El perfil '{profile_name}' no existe en {profiles_dir}.")
        
    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return Profile(**data)

def get_available_profiles() -> List[str]:
    profiles_dir = _get_profiles_dir()
    if not profiles_dir.exists():
        return []
    return [f.stem for f in profiles_dir.glob("*.yaml")]
