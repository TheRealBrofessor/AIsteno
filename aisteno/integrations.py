"""Small integration adapters for agent frameworks and JSON/stdin workflows."""

from __future__ import annotations

from typing import Any, Mapping

from .facts import facts_to_json
from .pack import pack


def pack_json(text: str) -> str:
    result = pack(text)
    return facts_to_json(result.facts)


def as_agent_memory(text: str) -> Mapping[str, Any]:
    result = pack(text)
    return {
        "memory": result.text,
        "facts": [fact.as_dict() for fact in result.facts],
        "schema_version": "1.0",
    }
