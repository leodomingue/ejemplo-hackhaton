#!/usr/bin/env python3
"""
Serve the Crisis Simulator frontend on http://localhost:3000
No dependencies beyond Python standard library.

Usage:
    python serve.py          # port 3000
    python serve.py 8080     # custom port
"""
import http.server
import socketserver
import os
import sys
import webbrowser
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
FRONTEND_DIR = Path(__file__).parent / "Crisis Simulator"

if not FRONTEND_DIR.exists():
    print(f"ERROR: No se encontró la carpeta '{FRONTEND_DIR}'")
    sys.exit(1)

os.chdir(FRONTEND_DIR)

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence per-request noise

print(f"")
print(f"  Crisis Simulator — Frontend")
print(f"  ───────────────────────────────────")
print(f"  URL:     http://localhost:{PORT}")
print(f"  Backend: http://localhost:8000  (debe estar corriendo)")
print(f"  Docs:    http://localhost:8000/docs")
print(f"")
print(f"  Ctrl+C para detener")
print(f"")

webbrowser.open(f"http://localhost:{PORT}")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
