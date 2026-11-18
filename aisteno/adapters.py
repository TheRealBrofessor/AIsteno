"""Agent adapters that keep integrations separate from the compiler."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import Config
from .sync import SyncResult, sync


def sync_hermes(config: Config, *, force: bool = False) -> SyncResult:
    if config.agent.casefold() != "hermes":
        raise ValueError("Hermes adapter requires config.agent='hermes'")
    return sync(config, force=force)


def agent_startup(config: Config) -> str:
    """Return verified packed context for an agent startup hook."""
    source = Path(config.source).expanduser().resolve()
    output = Path(config.output).expanduser().resolve()
    if source == output:
        raise ValueError("configured source and output must be different")
    data = output.read_text(encoding="utf-8")
    lines = data.splitlines()
    if len(lines) < 2 or lines[0] != "AISTENO-SYNC/v1":
        raise ValueError("context output is not an AIsteno-managed snapshot")
    prefix = "source-sha256:"
    if not lines[1].startswith(prefix):
        raise ValueError("context output is missing its source checksum")
    expected = lines[1][len(prefix):]
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if expected != actual:
        raise ValueError("context output is stale for the configured source")
    return "\n".join(lines[2:]) + ("\n" if len(lines) > 2 else "")
