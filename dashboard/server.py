"""Local read-only dashboard server (stdlib only, bound to 127.0.0.1).

    python -m dashboard                 # port from swarmtier.toml (dashboard_port, default 8790)
    python -m dashboard --port 9000
    python -m dashboard --ledger path/to/ledger.jsonl

Routes:
    /         the board (HTML)
    /state    board state as JSON
    /events   Server-Sent Events: one state message whenever the ledger changes
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from core import config, ledger  # noqa: E402
from dashboard.state import load_state  # noqa: E402

HOST = "127.0.0.1"
DEFAULT_PORT = 8790
SSE_POLL_S = 1.0
SSE_KEEPALIVE_S = 15.0


def make_server(port: int, ledger_path=None) -> ThreadingHTTPServer:
    """Build (not start) the server. ``port=0`` picks a free port."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the terminal quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _state_json(self) -> str:
            return json.dumps(load_state(ledger_path), ensure_ascii=False)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            try:
                if path in ("/", "/index.html"):
                    html = (ROOT / "index.html").read_bytes()
                    self._send(200, html, "text/html; charset=utf-8")
                elif path == "/state":
                    self._send(200, self._state_json().encode("utf-8"),
                               "application/json; charset=utf-8")
                elif path == "/events":
                    self._stream()
                else:
                    self._send(404, b"not found", "text/plain; charset=utf-8")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            target = Path(ledger_path) if ledger_path else ledger.ledger_path()
            last_sig, last_sent = None, 0.0
            while True:
                try:
                    st = target.stat()
                    sig = (st.st_mtime_ns, st.st_size)
                except OSError:
                    sig = None
                now = time.monotonic()
                if sig != last_sig:
                    last_sig, last_sent = sig, now
                    self.wfile.write(("data: %s\n\n" % self._state_json()).encode("utf-8"))
                elif now - last_sent > SSE_KEEPALIVE_S:
                    last_sent = now
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                time.sleep(SSE_POLL_S)

    srv = ThreadingHTTPServer((HOST, port), Handler)
    srv.daemon_threads = True
    return srv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dashboard",
                                 description="Local read-only board over the swarmtier ledger.")
    ap.add_argument("--port", type=int, default=None,
                    help="port (default: dashboard_port in swarmtier.toml, else %d)" % DEFAULT_PORT)
    ap.add_argument("--ledger", default=None, help="ledger file (default: <data dir>/ledger.jsonl)")
    a = ap.parse_args(argv)
    port = a.port if a.port is not None else int(config.load_config().get("dashboard_port", DEFAULT_PORT))
    try:
        srv = make_server(port, a.ledger)
    except OSError as exc:
        print("cannot listen on %s:%d (%s)" % (HOST, port, exc), file=sys.stderr)
        return 1
    print("swarmtier dashboard: http://%s:%d/  (Ctrl+C to stop)" % (HOST, srv.server_address[1]))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
