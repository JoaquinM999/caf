"""Diagnostico de la API key de Caf.  Ponelo en backend/ y corre:  python diagnostico_key.py

1) Muestra de DONDE puede venir la clave (solo los ultimos 4 caracteres, nunca la clave completa).
2) Prueba cada clave distinta: validez (listar modelos, no gasta tokens) y conexion Live.
"""
import asyncio
import os
from pathlib import Path

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parent


def ultimos4(k):
    return f"...{k[-4:]}" if k else "(vacia / no existe)"


def fuentes():
    f = {}
    try:
        import keyring
        f["Windows (keyring)"] = keyring.get_password("fr.louisraille.coucou", "caf-api-key")
    except Exception:
        f["Windows (keyring)"] = None
    f["variable de entorno GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")
    for nombre, ruta in [("backend/.env", BACKEND / ".env"),
                         ("Caf/.env", BACKEND.parent / "Caf" / ".env"),
                         (".env de la raiz", BACKEND.parent / ".env")]:
        f[nombre] = dotenv_values(ruta).get("GEMINI_API_KEY") if ruta.exists() else None
    return f


async def probar(key):
    from google import genai

    client = genai.Client(api_key=key)
    try:
        n = sum(1 for _ in client.models.list())
        print(f"   clave valida: ve {n} modelos")
    except Exception as e:
        print(f"   la clave NO funciona para listar modelos: {str(e)[:160]}")
        return
    try:
        async with client.aio.live.connect(model="gemini-3.8-live",
                                           config={"response_modalities": ["AUDIO"]}) as s:
            await s.send_realtime_input(text="hola")
            await asyncio.wait_for(anext(s.receive().__aiter__()), timeout=15)
            print("   Live (gemini-3.8-live): FUNCIONA")
    except Exception as e:
        print(f"   Live (gemini-3.8-live): FALLA -> {str(e)[:300]}")


async def main():
    f = fuentes()
    print("Origen de la clave                      Termina en")
    for nombre, k in f.items():
        print(f"  {nombre:38} {ultimos4(k)}")
    print("\nCompara con la clave del proyecto NUEVO en AI Studio (ultimos 4 caracteres).\n")
    for k in dict.fromkeys(v for v in f.values() if v):
        print(f"Probando la clave que termina en {ultimos4(k)}")
        await probar(k)


asyncio.run(main())
