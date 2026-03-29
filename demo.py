# demo.py
import subprocess
import sys
import os
import time
import webbrowser
import platform

ROOT = os.path.dirname(os.path.abspath(__file__))
OVERLAY_DIR = os.path.join(ROOT, "hackitba-overlay")

NPM = "npm.cmd" if platform.system() == "Windows" else "npm"

procesos = []

def log(msg):
    print(f"\n[DEMO] {msg}")

def correr(comando, cwd, nombre):
    log(f"Levantando {nombre}...")
    p = subprocess.Popen(
        comando,
        cwd=cwd,
        stdout=None,
        stderr=None
    )
    procesos.append((nombre, p))
    return p

def esperar(segundos, motivo):
    print(f"         Esperando {segundos}s ({motivo})", end="", flush=True)
    for _ in range(segundos):
        time.sleep(1)
        print(".", end="", flush=True)
    print()

def verificar_dependencias():
    log("Verificando dependencias...")

    node = subprocess.run(["node", "--version"], capture_output=True, text=True)
    npm  = subprocess.run([NPM, "--version"],    capture_output=True, text=True)
    if node.returncode != 0 or npm.returncode != 0:
        print("         ✗ Node.js no está instalado.")
        print("         Descargalo en https://nodejs.org")
        sys.exit(1)
    print(f"         ✓ Node {node.stdout.strip()}, npm {npm.stdout.strip()}")

    nm = os.path.join(OVERLAY_DIR, "node_modules")
    if not os.path.exists(nm):
        log("Instalando dependencias de Electron (primera vez)...")
        subprocess.run([NPM, "install"], cwd=OVERLAY_DIR, check=True)
        print("         ✓ Dependencias instaladas")
    else:
        print("         ✓ node_modules ya existe")

def apagar_todo():
    print("\n\n[DEMO] Cerrando todos los procesos...")
    for nombre, p in procesos:
        p.terminate()
        print(f"         ✓ {nombre} cerrado")
    print("[DEMO] Demo finalizada.\n")

def main():
    print("""
╔══════════════════════════════════════════╗
║     HALeph — Script de Demo              ║
║     HackITBA 2025                        ║
╚══════════════════════════════════════════╝
    """)

    verificar_dependencias()

    # Abrir ventanas del browser
    log("Abriendo ventanas de demo...")
    webbrowser.open("https://calendar.google.com/calendar/u/3/r?pli=1")
    time.sleep(1)
    webbrowser.open("https://hackitba-demo.atlassian.net/jira/for-you")
    time.sleep(1)
    print("         ✓ Calendar y Jira abiertos")

    # Levantar HALeph
    correr(
        [NPM, "start"],
        cwd=OVERLAY_DIR,
        nombre="HALeph (Electron)"
    )
    esperar(3, "Electron iniciando")

    print("""
╔══════════════════════════════════════════╗
║  Todo listo. Instrucciones:              ║
║                                          ║
║  1. Iniciá sesión en Calendar y Jira     ║
║     con la cuenta de demo                ║
║  2. La ventana de HALeph ya está abierta ║
║  3. Ctrl+Shift+Space para mostrar/       ║
║     ocultar el overlay                   ║
║  4. Escribí el problema, por ejemplo:    ║
║                                          ║
║     "PROJ-04 se atrasó 3 días,           ║
║      deadline el viernes"                ║
║                                          ║
║  Presioná Ctrl+C para cerrar todo        ║
╚══════════════════════════════════════════╝
    """)

    try:
        while True:
            for nombre, p in procesos:
                if p.poll() is not None:
                    print(f"\n[DEMO] ⚠ {nombre} se cerró inesperadamente")
            time.sleep(2)

    except KeyboardInterrupt:
        apagar_todo()

if __name__ == "__main__":
    main()