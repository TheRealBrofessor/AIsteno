"""Approval-based setup discovery for local agent memory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .config import Config, save_config


@dataclass(frozen=True)
class Candidate:
    agent: str
    source: Path
    output: Path


def discover_candidates(home: Path | None = None) -> tuple[Candidate, ...]:
    root = home or Path.home()
    candidates: list[Candidate] = []
    locations = (
        ("hermes", root / ".hermes" / "memory.md"),
        ("hermes", root / ".config" / "hermes" / "memory.md"),
        ("hermes", root / ".local" / "share" / "hermes" / "memory.md"),
    )
    for agent, source in locations:
        if source.is_file():
            candidates.append(Candidate(agent, source, source.with_name("memory.aisteno.txt")))
    return tuple(candidates)


def approve_candidate(candidate: Candidate, *, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    answer = input(
        f"Use {candidate.agent} memory source {candidate.source} and write {candidate.output}? [y/N] "
    )
    return answer.strip().casefold() in {"y", "yes"}


def setup(
    *,
    home: Path | None = None,
    assume_yes: bool = False,
    source: Path | None = None,
    output: Path | None = None,
    config_path: Path | None = None,
) -> Config:
    candidate = None
    if source:
        candidate = Candidate("custom", source, output or source.with_name("memory.aisteno.txt"))
    else:
        candidates = discover_candidates(home)
        if not candidates:
            raise FileNotFoundError("no supported agent memory location detected")
        candidate = candidates[0]
    if not approve_candidate(candidate, assume_yes=assume_yes):
        raise PermissionError("setup cancelled")
    config = Config(str(candidate.source), str(candidate.output), candidate.agent)
    save_config(config, config_path)
    return config
