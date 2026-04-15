#!/usr/bin/env python3
"""
Levanta todo el Crisis Simulator de una sola vez:
  - Backend  FastAPI en http://localhost:8000
  - Frontend HTML    en http://localhost:3000

Usage:
    python start.py
"""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent


def run(*cmd, **kwargs):
    return subprocess.Popen(
        [sys.executable, *cmd],
        cwd=ROOT,
        **kwargs,
    )


if __name__ == "__main__":
    print("")
    print("  Crisis Simulator — Iniciando servicios...")
    print("")

    # 1. Backend
    backend = run(
        "-m", "uvicorn", "backend.main:app",
        "--reload", "--port", "8000",
        "--log-level", "warning",
    )
    print("  [1/2] Backend  arrancando en http://localhost:8000")
    time.sleep(2)  # dale tiempo a uvicorn para bindear el puerto

    # 2. Frontend (nuestro serve.py — sin deps extra)
    frontend = run("serve.py", "3000")
    print("  [2/2] Frontend arrancando en http://localhost:3000")
    time.sleep(1)

    print("")
    print("  ✓ Backend  → http://localhost:8000")
    print("  ✓ Frontend → http://localhost:3000")
    print("  ✓ API docs → http://localhost:8000/docs")
    print("")
    print("  Ctrl+C para detener todo")
    print("")

    webbrowser.open("http://localhost:3000")

    try:
        backend.wait()
    except KeyboardInterrupt:
        print("\n  Deteniendo servicios...")
        backend.terminate()
        frontend.terminate()
        print("  Listo.")
