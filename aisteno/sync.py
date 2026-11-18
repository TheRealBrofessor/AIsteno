"""Safe synchronization, snapshots, rollback, and verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import tempfile
import time

from .config import Config
from .pack import pack


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    source: Path
    output: Path
    backup: Path | None
    source_sha256: str
    output_sha256: str
    savings_percent: float


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _backup_path(output: Path, backup_dir: Path | None = None) -> Path:
    directory = backup_dir or output.parent / ".aisteno-backups"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"{output.name}.{stamp}.bak"


def sync(config: Config, *, force: bool = False) -> SyncResult:
    source = Path(config.source).expanduser().resolve()
    output = Path(config.output).expanduser().resolve()
    if source == output:
        raise ValueError("source and output must be different")
    original = source.read_bytes()
    existing = output.read_bytes() if output.exists() else None
    if existing is not None and not force and existing.startswith(b"AISTENO-SYNC"):
        previous = existing.split(b"\n", 2)[-1]
        if _digest(original) in existing.decode("utf-8", "ignore"):
            return SyncResult(False, source, output, None, _digest(original), _digest(existing), 0.0)
    result = pack(original.decode("utf-8"))
    payload = f"AISTENO-SYNC/v1\nsource-sha256:{_digest(original)}\n{result.text}".encode("utf-8")
    backup = None
    if existing is not None:
        backup = _backup_path(output, Path(config.backup_dir).expanduser() if config.backup_dir else None)
        shutil.copy2(output, backup)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".aisteno-", dir=output.parent)
    try:
        with open(fd, "wb", closefd=True) as stream:
            stream.write(payload)
        Path(temporary).replace(output)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    saved = len(original) - len(payload)
    return SyncResult(True, source, output, backup, _digest(original), _digest(payload), saved / len(original) * 100 if original else 0.0)


def restore(backup: Path, output: Path) -> None:
    backup = backup.expanduser().resolve()
    output = output.expanduser().resolve()
    if backup == output:
        raise ValueError("backup and output must be different")
    if not backup.is_file():
        raise FileNotFoundError(backup)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, output)


def watch(config: Config, *, interval: float = 2.0, once: bool = False):
    """Synchronize after source changes; keeps the source file untouched."""
    previous = None
    while True:
        digest = _digest(Path(config.source).expanduser().read_bytes())
        if digest != previous:
            result = sync(config)
            previous = digest
            yield result
        if once:
            return
        time.sleep(interval)
