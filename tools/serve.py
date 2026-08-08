#!/usr/bin/env python3
"""Kleiner lokaler Vorschau-Server (nur fuer die Entwicklung)."""
import functools
import http.server
import os
import socketserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("PORT", "4321"))

os.chdir(ROOT)
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
    print(f"Serving {ROOT} on http://localhost:{PORT}")
    httpd.serve_forever()
