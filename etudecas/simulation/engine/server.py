#!/usr/bin/env python3
"""Authenticated, bounded local HTTP API for interactive simulation runs."""
from __future__ import annotations

import argparse
from functools import partial
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import socket
import subprocess
import threading
from typing import Any
from urllib.parse import urlsplit

from .api import simulate
from .bounded_execution import run_simulation_bounded
from .http_contract import REPO_ROOT, request_from_http


class SimulationApiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, *, input_root=REPO_ROOT,
                 output_root=REPO_ROOT / 'etudecas/simulation/result/_api_runs',
                 token=None, allowed_origins=(), max_body_bytes=4 * 1024 * 1024,
                 max_days=3660, execution_timeout=300.0, read_timeout=10.0):
        if address[0] not in {'127.0.0.1', 'localhost'}:
            raise ValueError('The simulation API must bind to IPv4 loopback')
        for value in (max_body_bytes, max_days):
            if type(value) is not int or value <= 0:
                raise ValueError('Limits must be positive integers')
        for value in (execution_timeout, read_timeout):
            if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
                raise ValueError('Timeouts must be finite and positive')
        for origin in allowed_origins:
            parsed = urlsplit(origin)
            if origin != 'null' and (parsed.scheme not in {'http', 'https'} or not parsed.netloc
                                      or parsed.path or parsed.query or parsed.fragment or parsed.username):
                raise ValueError('Origins must be exact HTTP(S) origins or explicit null')
        if token is not None and (not isinstance(token, str) or len(token) < 16 or not token.isascii()):
            raise ValueError('Token must contain at least 16 ASCII characters')
        self.input_root = Path(input_root).resolve()
        self.output_root = Path(output_root).resolve()
        self.token = token or secrets.token_urlsafe(32)
        self.allowed_origins = frozenset(allowed_origins)
        self.max_body_bytes = max_body_bytes
        self.max_days = max_days
        self.execution_timeout = execution_timeout
        self.read_timeout = read_timeout
        self.execution_slot = threading.BoundedSemaphore(1)
        super().__init__(address, SimulationApiHandler)


class SimulationApiHandler(BaseHTTPRequestHandler):
    server_version = 'EtudecasSimulationAPI/0.2'

    def setup(self):
        super().setup()
        self.connection.settimeout(self.server.read_timeout)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def finish(self):
        # Half-close the response before draining a bounded amount of unread
        # request data, avoiding a Windows TCP reset discarding an early error.
        try:
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
            self.connection.settimeout(.1)
            remaining = 65536
            while remaining > 0:
                chunk = self.connection.recv(min(8192, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass
        finally:
            super().finish()

    def _headers(self, status=200, length=0):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(length))
        self.send_header('Connection', 'close')
        self.send_header('Vary', 'Origin')
        origin = self.headers.get('Origin')
        if origin in self.server.allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Etudecas-Token')
        self.end_headers()

    def _write_json(self, payload, status=200):
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self._headers(status, len(encoded))
        self.wfile.write(encoded)

    def _check_origin_and_host(self):
        port = self.server.server_port
        if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            self._write_json({'ok': False, 'error': 'host_forbidden'}, 403)
            return False
        origin = self.headers.get('Origin')
        if origin is not None and origin not in self.server.allowed_origins:
            self._write_json({'ok': False, 'error': 'origin_forbidden'}, 403)
            return False
        return True

    def do_OPTIONS(self):
        if self._check_origin_and_host():
            self._headers(204)

    def do_GET(self):
        if not self._check_origin_and_host():
            return
        if self.path.rstrip('/') == '/health':
            self._write_json({'ok': True, 'service': 'etudecas-simulation-api', 'authentication_required': True})
        else:
            self._write_json({'ok': False, 'error': 'not_found'}, 404)

    def do_POST(self):
        if not self._check_origin_and_host():
            return
        if self.path.rstrip('/') != '/simulate':
            self._write_json({'ok': False, 'error': 'not_found'}, 404)
            return
        provided = self.headers.get('X-Etudecas-Token', '')
        if not hmac.compare_digest(provided.encode('utf-8'), self.server.token.encode('utf-8')):
            self._write_json({'ok': False, 'error': 'authentication_required'}, 401)
            return
        lengths = self.headers.get_all('Content-Length', [])
        if (self.headers.get('Transfer-Encoding') or len(lengths) != 1
                or not lengths[0].isascii() or not lengths[0].isdecimal()
                or len(lengths[0]) > 20):
            self._write_json({'ok': False, 'error': 'invalid_content_length'}, 400)
            return
        length = int(lengths[0])
        if not 0 < length <= self.server.max_body_bytes:
            self._write_json({'ok': False, 'error': 'body_too_large_or_empty'}, 413)
            return
        if self.headers.get_content_type() != 'application/json':
            self._write_json({'ok': False, 'error': 'application_json_required'}, 415)
            return
        if not self.server.execution_slot.acquire(blocking=False):
            self._write_json({'ok': False, 'error': 'simulation_busy'}, 429)
            return
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError('Incomplete request body')
            payload = json.loads(body.decode('utf-8'))
            request = request_from_http(payload, input_root=self.server.input_root,
                                        output_root=self.server.output_root, max_days=self.server.max_days)
            result = simulate(request, run_executor=partial(
                run_simulation_bounded, timeout_seconds=self.server.execution_timeout))
            self._write_json({'ok': True, 'result': result.to_dict()})
        except subprocess.TimeoutExpired:
            self._write_json({'ok': False, 'error': 'simulation_timeout'}, 504)
        except (socket.timeout, TimeoutError):
            self._write_json({'ok': False, 'error': 'request_timeout'}, 408)
        except (ValueError, UnicodeError, RecursionError, OverflowError) as exc:
            self._write_json({'ok': False, 'error': str(exc)}, 400)
        except Exception:
            self._write_json({'ok': False, 'error': 'simulation_failed'}, 500)
        finally:
            self.server.execution_slot.release()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=('127.0.0.1', 'localhost'), default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--input-root', type=Path, default=REPO_ROOT)
    parser.add_argument('--output-root', type=Path, default=REPO_ROOT / 'etudecas/simulation/result/_api_runs')
    parser.add_argument('--allow-origin', action='append', default=[])
    parser.add_argument('--max-days', type=int, default=3660)
    parser.add_argument('--max-body-bytes', type=int, default=4 * 1024 * 1024)
    parser.add_argument('--execution-timeout', type=float, default=300.0)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    with SimulationApiServer((args.host, args.port), input_root=args.input_root,
                             output_root=args.output_root, allowed_origins=args.allow_origin,
                             max_days=args.max_days, max_body_bytes=args.max_body_bytes,
                             execution_timeout=args.execution_timeout) as server:
        print(f'[OK] API: http://{args.host}:{server.server_port}', flush=True)
        print(f'[LOCAL] X-Etudecas-Token: {server.token}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
