import argparse
import asyncio
import logging

from caf.engine import CafEngine


async def print_events(engine):
    """Muestra en consola lo que pasa: estados, transcripciones y herramientas."""
    ult_rol, linea = None, ""
    while True:
        ev = await engine.events_queue.get()
        if "estado" in ev:
            print(f"\n[estado] {ev['estado']} {ev.get('detalle', '')}".rstrip())
        elif "transcripcion" in ev:
            t = ev["transcripcion"]
            if t["rol"] != ult_rol:
                print(f"\n{'Vos' if t['rol'] == 'usuario' else 'Caf'}: ", end="", flush=True)
                ult_rol = t["rol"]
            print(t["texto"], end="", flush=True)
        elif "modo" in ev:
            print(f"\n[modo] {ev['modo']}")
        elif "herramienta" in ev:
            h = ev["herramienta"]
            print(f"\n[herramienta] {h['nombre']} -> {h['resultado']}")


async def read_stdin(engine):
    """Escribi un mensaje y Enter para probar sin micrófono."""
    while True:
        texto = await asyncio.to_thread(input)
        if texto.strip():
            engine.text_in_queue.put_nowait(texto.strip())


async def run_console():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="amiguito", help="Nombre del perfil a cargar")
    parser.add_argument("--sin-audio", action="store_true", help="Solo texto (sin mic ni parlantes)")
    parser.add_argument("--debug", action="store_true", help="Logs detallados")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("websockets").setLevel(logging.WARNING)

    engine = CafEngine(profile_name=args.profile, use_audio_hardware=not args.sin_audio)
    print("Caf V2 listo. Decí \"Caf\" para activarlo (o escribí un mensaje y Enter). Ctrl+C para salir.")
    helpers = [asyncio.create_task(print_events(engine)), asyncio.create_task(read_stdin(engine))]
    try:
        await engine.start()
    finally:
        engine.stop()
        for h in helpers:
            h.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(run_console())
    except KeyboardInterrupt:
        print("\nSaliendo...")
