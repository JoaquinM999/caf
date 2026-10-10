import os
import sys
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def get_repo_content(repo_path):
    """Lee los archivos del proyecto y los formatea para el agente."""
    code_content = ""
    ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', 'env', '.next', 'target'}
    valid_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.rs', '.yaml'}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in valid_extensions):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        relative_path = os.path.relpath(file_path, repo_path)
                        code_content += f"\n\n--- Archivo: {relative_path} ---\n"
                        code_content += f.read()
                except Exception as e:
                    print(f"Omitiendo {file} (no se pudo leer: {e})")
                    
    return code_content

def optimize_and_secure_kaf(repo_path):
    print("1. Escaneando y leyendo archivos locales de Kaf...")
    repo_code = get_repo_content(repo_path)
    
    if not repo_code.strip():
        print("Error: No se encontró código válido para analizar en este directorio.")
        return

    agent_task = f"""
    Eres un agente ingeniero de software senior trabajando en la optimización, reparación y securización del asistente 'Kaf', integrado en Coucou.
    
    A continuación te proporciono el código actual del repositorio. Tu misión es analizarlo, indicarme exactamente qué partes están fallando y generar el código final corregido para que yo lo reemplace.
    
    1. Lectura: Analiza exhaustivamente la estructura y lógica de Kaf.
    2. Depuración: Identifica y elimina código muerto, redundante o ineficiente.
    3. Implementación 100%: Corrige problemas actuales. Programa la capacidad para que Kaf busque y reproduzca pistas en Spotify de manera fiable y realice búsquedas dinámicas precisas en Google.
    4. Seguridad y Testing: Asegura que el código sea 100% seguro, no desvaríe en su control del sistema local y valida todo mediante sugerencias de tests unitarios y de integración.
    
    CÓDIGO ACTUAL DEL PROYECTO:
    {repo_code}
    """

    # Archivo donde se guardará toda la respuesta
    output_txt = "resultado_antigravity.txt"
    print(f"2. Enviando el código al entorno remoto... Guardando respuesta en '{output_txt}'")
    print("\n--- Respuesta del Agente en tiempo real ---\n")

    try:
        interaction = client.interactions.create(
            agent="antigravity-preview-09-2026",
            input=agent_task,
            environment={"type": "remote"},
            stream=True
        )

        # Abre el archivo en modo escritura
        with open(output_txt, "w", encoding="utf-8") as f:
            for event in interaction:
                if event.event_type == "step.delta" and hasattr(event.delta, 'text'):
                    chunk = event.delta.text
                    
                    # Imprime en la terminal
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    
                    # Guarda en el archivo txt en tiempo real
                    f.write(chunk)
                    f.flush()

        print(f"\n\nProceso finalizado. Todo el código generado se guardó enterito en '{output_txt}'.")

    except Exception as e:
        print(f"\nError crítico durante la ejecución con la API: {e}")

if __name__ == "__main__":
    # Apuntamos directamente a la subcarpeta 'backend'
    target_path = os.path.join(os.getcwd(), "backend")
    
    if not os.path.exists(target_path):
        print(f"Error: No se encontró la carpeta {target_path}. Verifica estar en la raíz de 'Coucou'.")
    else:
        optimize_and_secure_kaf(target_path)