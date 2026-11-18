"""Agent adapters that keep integrations separate from the compiler."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .sync import SyncResult, _snapshot_parts, _digest, sync


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
    data = output.read_bytes()
    snapshot = _snapshot_parts(data)
    if snapshot is None:
        raise ValueError("context output is not an AIsteno-managed snapshot")
    expected_source, expected_body, body = snapshot
    if expected_source != _digest(source.read_bytes()):
        raise ValueError("context output is stale for the configured source")
    if expected_body != _digest(body):
        raise ValueError("context output has been modified")
    return body.decode("utf-8")
