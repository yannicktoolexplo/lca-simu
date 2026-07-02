#!/usr/bin/env python3
"""Small local HTTP API for interactive simulation runs."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any

from etudecas.simulation.engine.api import request_from_dict, simulate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Etudecas simulation API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


class SimulationApiHandler(BaseHTTPRequestHandler):
    server_version = "EtudecasSimulationAPI/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the local server quiet by default; callers get structured errors.
        return

    def _headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        self._headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._headers(204)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._write_json({"ok": True, "service": "etudecas-simulation-api"})
            return
        self._write_json({"ok": False, "error": "not_found"}, status=404)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/simulate":
            self._write_json({"ok": False, "error": "not_found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object.")
            result = simulate(request_from_dict(payload))
            self._write_json({"ok": True, "result": result.to_dict()})
        except Exception as exc:
            self._write_json({"ok": False, "error": str(exc)}, status=400)


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SimulationApiHandler)
    print(f"[OK] Etudecas simulation API listening on http://{args.host}:{args.port}")
    print("[INFO] GET /health, POST /simulate")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
