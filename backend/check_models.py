import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
r = requests.get(url)
data = r.json()
models = data.get("models", [])
bidi_models = [m["name"] for m in models if "bidiGenerateContent" in m.get("supportedGenerationMethods", [])]
print("Bidi models:")
for b in bidi_models:
    print(b)
