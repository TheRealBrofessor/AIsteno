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


def _error(request_id, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_error(None, -32700, "Parse error")) + "\n")
            stdout.flush()
            continue
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            stdout.write(json.dumps(_error(None, -32600, "Invalid Request")) + "\n")
            stdout.flush()
            continue
        request_id = request.get("id")
        if "id" not in request:
            continue
        method = request.get("method")
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "aisteno", "version": "0.6.0"},
            }
        elif method == "tools/list":
            result = {"tools": [{"name": "memory_context", "description": "Read verified AIsteno context.", "inputSchema": {"type": "object"}}]}
        elif method == "tools/call" and request.get("params", {}).get("name") == "memory_context":
            try:
                context = agent_startup(load_config())
            except Exception:
                stdout.write(json.dumps(_error(request_id, -32603, "Unable to load verified memory context")) + "\n")
                stdout.flush()
                continue
            result = {"content": [{"type": "text", "text": context}]}
        elif method == "resources/list":
            result = {"resources": [{"uri": "aisteno://memory/context", "name": "Verified memory context", "mimeType": "text/plain"}]}
        elif method == "resources/read" and request.get("params", {}).get("uri") == "aisteno://memory/context":
            try:
                context = agent_startup(load_config())
            except Exception:
                stdout.write(json.dumps(_error(request_id, -32603, "Unable to load verified memory context")) + "\n")
                stdout.flush()
                continue
            result = {"contents": [{"uri": "aisteno://memory/context", "text": context}]}
        elif method == "resources/read":
            stdout.write(json.dumps(_error(request_id, -32602, "Unknown resource URI")) + "\n")
            stdout.flush()
            continue
        elif method == "tools/call":
            stdout.write(json.dumps(_error(request_id, -32602, "Unknown tool")) + "\n")
            stdout.flush()
            continue
        else:
            stdout.write(json.dumps(_error(request_id, -32601, "Method not found")) + "\n")
            stdout.flush()
            continue
        stdout.write(json.dumps(_response(request_id, result)) + "\n")
        stdout.flush()
