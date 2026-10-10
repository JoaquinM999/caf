import re
from pathlib import Path
import os

def apply_changes():
    input_file = Path(r"c:\Users\Joako\OneDrive\Escritorio\Coucou\resultado_antigravity.txt")
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    # The file has sections like:
    # #### Archivo: `filename`
    # ```language
    # code
    # ```
    
    # Regex to capture filename and code
    pattern = re.compile(r"#### Archivo: `([^`]+)`\s*```[a-z]*\s*(.*?)\s*```", re.DOTALL)
    
    base_dir = Path(r"c:\Users\Joako\OneDrive\Escritorio\Coucou\backend")
    
    for match in pattern.finditer(content):
        filename = match.group(1).strip()
        code = match.group(2).strip() + "\n"
        
        file_path = base_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Escribiendo {file_path}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
            
    # Delete the dead scripts mentioned
    files_to_delete = [
        base_dir / "check_models.py",
        base_dir / "check_types.py",
        base_dir / "list_models.py"
    ]
    
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"Eliminado: {f}")

if __name__ == "__main__":
    apply_changes()
