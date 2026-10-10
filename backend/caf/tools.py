import os
import yaml
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

# Configuración de carpeta segura
WORKSPACE_DIR = Path.home() / "CafWorkspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

def load_whitelist():
    if not CONFIG_PATH.exists():
        # Crear config por defecto
        default_config = {
            "programas": {
                "spotify": "explorer.exe shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
                "bloc de notas": "notepad.exe",
                "calculadora": "calc.exe"
            }
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f)
        return default_config["programas"]
        
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config.get("programas", {})

def _safe_resolve(relative_path: str) -> Path:
    """Resuelve la ruta relativa y asegura que esté dentro de WORKSPACE_DIR."""
    # Convertir a Path y resolver
    target = (WORKSPACE_DIR / relative_path).resolve()
    # Comprobar que WORKSPACE_DIR sea un padre estricto o el mismo
    try:
        target.relative_to(WORKSPACE_DIR.resolve())
    except ValueError:
        raise ValueError(f"Acceso denegado: {relative_path} está fuera de la carpeta de trabajo.")
    return target

def abrir_programa(nombre: str) -> str:
    """Abre un programa según la lista blanca. Retorna el resultado."""
    whitelist = load_whitelist()
    nombre = nombre.lower()
    
    if nombre not in whitelist:
        return f"Error: El programa '{nombre}' no está en la lista blanca de permitidos."
        
    comando = whitelist[nombre]
    try:
        # En Windows shell=False es más seguro. Si usa explorer.exe, necesitamos dividir los argumentos.
        # Por simplicidad usamos powershell de forma segura sin interpolación.
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", comando], 
                                capture_output=True, text=True, timeout=10)
        return f"Éxito: {nombre} ejecutado." if result.returncode == 0 else f"Error al ejecutar: {result.stderr.strip()}"
    except Exception as e:
        return f"Excepción al ejecutar {nombre}: {str(e)}"

def spotify_buscar(consulta: str) -> str:
    """Abre Spotify en los resultados de busqueda de `consulta` (no reproduce sola)."""
    consulta = (consulta or "").strip()
    if not consulta:
        return "Error: falta el texto a buscar."
    uri = "spotify:search:" + quote(consulta)  # el texto va codificado: no puede inyectar comandos
    try:
        if sys.platform == "win32":
            os.startfile(uri)
        else:
            subprocess.run(["xdg-open", uri], timeout=10)
        return f"Éxito: busqué '{consulta}' en Spotify (queda en la pantalla de resultados)."
    except Exception as e:
        return f"Error al abrir Spotify: {e}"


def crear_archivo(ruta_relativa: str, contenido: str) -> str:
    """Crea o sobreescribe un archivo en la carpeta segura de trabajo."""
    try:
        target = _safe_resolve(ruta_relativa)
        # Crear carpetas padre si no existen
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(contenido)
        return f"Éxito: Archivo {target.name} guardado en la carpeta de trabajo."
    except Exception as e:
        return f"Error al crear archivo: {str(e)}"

def leer_archivo(ruta_relativa: str) -> str:
    """Lee el contenido de un archivo en la carpeta de trabajo."""
    try:
        target = _safe_resolve(ruta_relativa)
        if not target.is_file():
            return f"Error: No se encontró el archivo '{ruta_relativa}'."
        with open(target, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error al leer archivo: {str(e)}"

def listar_archivos(ruta_relativa: str = ".") -> str:
    """Lista los archivos dentro de la carpeta segura."""
    try:
        target = _safe_resolve(ruta_relativa)
        if not target.is_dir():
            return f"Error: '{ruta_relativa}' no es una carpeta."
        items = os.listdir(target)
        if not items:
            return "La carpeta está vacía."
        return "\\n".join(items)
    except Exception as e:
        return f"Error al listar archivos: {str(e)}"

def generar_reporte(titulo: str, contenido_markdown: str, formato: str = "md") -> str:
    """Genera un reporte markdown en la carpeta segura."""
    try:
        import re
        formato = formato if formato in ("md", "txt") else "md"
        safe_title = re.sub(r"[^\w\-]+", "_", titulo, flags=re.UNICODE).strip("_") or "reporte"
        filename = f"{safe_title}.{formato}"
        target = _safe_resolve(filename)
        with open(target, "w", encoding="utf-8") as f:
            f.write(f"# {titulo}\\n\\n{contenido_markdown}")
        return f"Reporte generado exitosamente como '{filename}' en la carpeta de trabajo."
    except Exception as e:
        return f"Error al generar reporte: {str(e)}"

def borrar_archivo(ruta_relativa: str, confirmacion: str = "no") -> str:
    """Requiere confirmación explícita para borrar."""
    if confirmacion.lower() not in ["si", "sí", "yes"]:
        return "pendiente_confirmacion: Acción destructiva. Por favor pida confirmación explícita al usuario diciendo '¿Estás seguro que querés borrar este archivo?'"
    try:
        target = _safe_resolve(ruta_relativa)
        if target.is_file():
            target.unlink()
            return f"Éxito: Archivo '{ruta_relativa}' eliminado."
        return f"Error: Archivo '{ruta_relativa}' no encontrado."
    except Exception as e:
        return f"Error al borrar: {str(e)}"