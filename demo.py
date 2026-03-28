# demo.py
import subprocess
import sys
import os
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
OVERLAY_DIR = os.path.join(ROOT, "hackitba-overlay")
BACKEND_DIR = os.path.join(ROOT, "backend")
MOCK_DIR = os.path.join(ROOT, "hackitba-overlay", "hackitba-mock")

procesos = []

def log(msg):
    print(f"\n[DEMO] {msg}")

def correr(comando, cwd, nombre):
    log(f"Levantando {nombre}...")
    p = subprocess.Popen(
        comando,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
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
    
    # Python
    try:
        import flask, flask_cors, requests, rich
        print("         ✓ Python: flask, flask_cors, requests, rich")
    except ImportError as e:
        print(f"         ✗ Falta instalar: {e}")
        print("         Corré: pip install flask flask-cors requests rich")
        sys.exit(1)

    # Node / npm
    node = subprocess.run(["node", "--version"], capture_output=True, text=True)
    npm  = subprocess.run(["npm", "--version"],  capture_output=True, text=True)
    if node.returncode != 0 or npm.returncode != 0:
        print("         ✗ Node.js no está instalado.")
        print("         Descargalo en https://nodejs.org")
        sys.exit(1)
    print(f"         ✓ Node {node.stdout.strip()}, npm {npm.stdout.strip()}")

    # node_modules de Electron
    nm = os.path.join(OVERLAY_DIR, "node_modules")
    if not os.path.exists(nm):
        log("Instalando dependencias de Electron (primera vez, puede tardar)...")
        subprocess.run(["npm", "install"], cwd=OVERLAY_DIR, check=True)
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

    # 1. Backend Flask (P3)
    correr(
        [sys.executable, "app.py"],
        cwd=BACKEND_DIR,
        nombre="Backend Flask (P3)"
    )
    esperar(2, "backend iniciando")

    # 2. Mock server (fallback por si el backend falla)
    correr(
        [sys.executable, "mock_server.py"],
        cwd=MOCK_DIR,
        nombre="Mock server (fallback)"
    )
    esperar(1, "mock iniciando")

    # 3. HALeph (Electron)
    correr(
        ["npm", "start"],
        cwd=OVERLAY_DIR,
        nombre="HALeph (Electron)"
    )
    esperar(3, "Electron iniciando")

    print("""
╔══════════════════════════════════════════╗
║  Todo levantado. Instrucciones:          ║
║                                          ║
║  1. La ventana de HALeph ya está abierta ║
║  2. Presioná Ctrl+Shift+Space para       ║
║     mostrarla/ocultarla                  ║
║  3. Escribí el problema en el campo      ║
║     de texto, por ejemplo:               ║
║                                          ║
║     "PROJ-04 se atrasó 3 días,           ║
║      deadline el viernes"                ║
║                                          ║
║  4. Revisá Calendar y Jira para ver      ║
║     los cambios aplicados                ║
║                                          ║
║  Presioná Ctrl+C para cerrar todo        ║
╚══════════════════════════════════════════╝
    """)

    try:
        # Mantener el script corriendo hasta Ctrl+C
        while True:
            # Verificar si algún proceso murió inesperadamente
            for nombre, p in procesos:
                if p.poll() is not None:
                    print(f"\n[DEMO] ⚠ {nombre} se cerró inesperadamente")
            time.sleep(2)

    except KeyboardInterrupt:
        apagar_todo()

if __name__ == "__main__":
    main()