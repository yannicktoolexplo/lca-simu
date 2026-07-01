#!/usr/bin/env python3
"""Launch the interactive Etudecas map with a local simulation API server."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


DEFAULT_HTML = (
    "etudecas/simulation/result/_codex_lot_trace_5y_risk_portfolio/maps/"
    "supply_graph_lot_trace_5y_risk_portfolio.interactive_whatif.html"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start local simulation API and open an Etudecas map.")
    parser.add_argument("--html", default=DEFAULT_HTML, help="HTML map to open.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Start server without opening the browser.")
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    return parser.parse_args()


def health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/health"


def server_is_ready(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with urlopen(health_url(host, port), timeout=timeout) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def wait_for_server(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server_is_ready(host, port, timeout=0.5):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Simulation API did not answer on {health_url(host, port)}")


def start_server(host: str, port: int, cwd: Path) -> subprocess.Popen[str] | None:
    if server_is_ready(host, port):
        print(f"[INFO] Reusing existing simulation API at {health_url(host, port)}")
        return None
    cmd = [
        sys.executable,
        "-m",
        "etudecas.simulation.engine.server",
        "--host",
        host,
        "--port",
        str(port),
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        text=True,
    )


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    html_path = (repo_root / args.html).resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"HTML map not found: {html_path}")

    proc = start_server(args.host, args.port, cwd=repo_root)
    try:
        wait_for_server(args.host, args.port, args.startup_timeout)
        print(f"[OK] Simulation API ready: {health_url(args.host, args.port)}")
        print(f"[OK] Map: {html_path}")
        if not args.no_browser:
            webbrowser.open(html_path.as_uri())
        print("[INFO] Keep this window open while using live simulation features.")
        print("[INFO] Press Ctrl+C here to stop the local server when finished.")
        if proc is not None:
            proc.wait()
        else:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping launcher.")
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
