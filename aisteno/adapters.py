"""Agent adapters that keep integrations separate from the compiler."""

from __future__ import annotations

from .config import Config
from .sync import SyncResult, sync


def sync_hermes(config: Config, *, force: bool = False) -> SyncResult:
    if config.agent.casefold() != "hermes":
        raise ValueError("Hermes adapter requires config.agent='hermes'")
    return sync(config, force=force)


def agent_startup(config: Config) -> str:
    """Return verified packed context for an agent startup hook."""
    return open(config.output, encoding="utf-8").read()
