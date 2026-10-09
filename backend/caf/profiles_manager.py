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

def load_profile(profile_name: str) -> Profile:
    profiles_dir = Path(__file__).parent / "profiles"
    profile_path = profiles_dir / f"{profile_name}.yaml"
    
    if not profile_path.exists():
        raise FileNotFoundError(f"El perfil '{profile_name}' no existe en {profiles_dir}.")
        
    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return Profile(**data)

def get_available_profiles() -> List[str]:
    profiles_dir = Path(__file__).parent / "profiles"
    if not profiles_dir.exists():
        return []
    return [f.stem for f in profiles_dir.glob("*.yaml")]
