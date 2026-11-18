"""Local-only dashboard for sync status and fact reports."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

from .config import load_config
from .pack import pack


def _page(config, result) -> str:
    facts = result.facts
    conflicts = sum(bool(fact.conflicts) for fact in facts)
    return f"""<!doctype html><meta charset="utf-8"><title>AIsteno</title>
<h1>AIsteno memory dashboard</h1>
<p><b>Source:</b> {config.source}</p><p><b>Output:</b> {config.output}</p>
<p><b>Facts:</b> {len(facts)} &nbsp; <b>Conflicts:</b> {conflicts}
&nbsp; <b>Warnings:</b> {result.possible_lost_detail_warnings}
&nbsp; <b>Secrets redacted:</b> {result.secrets_redacted}</p>
<pre>{json.dumps([fact.as_dict() for fact in facts], indent=2)}</pre>"""


def serve(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    config = load_config()
    source = Path(config.source)
    result = pack(source.read_text(encoding="utf-8"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path != "/":
                self.send_error(404)
                return
            body = _page(config, result).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    return server
