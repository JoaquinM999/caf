import requests

api_key = "AQ.Ab8RN6Jg_6FFDDW7zM6yiQfh-hUf3mLy6KAn3qerh70__an8Qw"


url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
resp = requests.get(url)
models = resp.json().get("models", [])
for m in models:
    name = m.get("name")
    methods = m.get("supportedGenerationMethods", [])
    if "bidiGenerateContent" in methods:
        print(f"Supported model v1beta: {name}")

url_alpha = f"https://generativelanguage.googleapis.com/v1alpha/models?key={api_key}"
resp_alpha = requests.get(url_alpha)
models_alpha = resp_alpha.json().get("models", [])
print(f"Total v1alpha models: {len(models_alpha)}")
for m in models_alpha:
    print(m.get("name"), m.get("supportedGenerationMethods"))

