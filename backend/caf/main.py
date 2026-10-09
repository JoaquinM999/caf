import asyncio
import argparse
from caf.engine import CafEngine

async def run_console():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="amiguito", help="Nombre del perfil a cargar")
    args = parser.parse_args()
    
    engine = CafEngine(profile_name=args.profile)
    try:
        await engine.start()
    except KeyboardInterrupt:
        print("\nSaliendo...")
    finally:
        engine.stop()

if __name__ == "__main__":
    try:
        asyncio.run(run_console())
    except KeyboardInterrupt:
        pass
