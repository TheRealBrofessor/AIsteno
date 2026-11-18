"""Minimal MCP-compatible JSON-RPC stdio bridge.

The bridge intentionally has no framework dependency: MCP clients can invoke
the standard initialize/tools/list/tools/call flow through stdin/stdout.
"""

from __future__ import annotations

import json
import sys

from .config import load_config
from .adapters import agent_startup


def _response(request_id, result) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        request = json.loads(line)
        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}, "resources": {}}}
        elif method == "tools/list":
            result = {"tools": [{"name": "memory_context", "description": "Read verified AIsteno context.", "inputSchema": {"type": "object"}}]}
        elif method == "tools/call" and request.get("params", {}).get("name") == "memory_context":
            result = {"content": [{"type": "text", "text": agent_startup(load_config())}]}
        elif method == "resources/list":
            result = {"resources": [{"uri": "aisteno://memory/context", "name": "Verified memory context", "mimeType": "text/plain"}]}
        elif method == "resources/read":
            result = {"contents": [{"uri": "aisteno://memory/context", "text": agent_startup(load_config())}]}
        else:
            result = {}
        stdout.write(json.dumps(_response(request_id, result)) + "\n")
        stdout.flush()
