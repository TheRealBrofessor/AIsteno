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


def _snapshot_parts(data: bytes) -> tuple[str, str, bytes] | None:
    lines = data.splitlines(keepends=True)
    if len(lines) < 3 or lines[0] != b"AISTENO-SYNC/v1\n":
        return None
    source_prefix = b"source-sha256:"
    packed_prefix = b"packed-sha256:"
    if not lines[1].startswith(source_prefix) or not lines[1].endswith(b"\n"):
        return None
    if not lines[2].startswith(packed_prefix) or not lines[2].endswith(b"\n"):
        return None
    source_hash = lines[1][len(source_prefix):-1].decode("ascii", "strict")
    packed_hash = lines[2][len(packed_prefix):-1].decode("ascii", "strict")
    return source_hash, packed_hash, b"".join(lines[3:])


def _backup_path(output: Path, backup_dir: Path | None = None) -> Path:
    directory = backup_dir or output.parent / ".aisteno-backups"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return directory / f"{output.name}.{stamp}.bak"


def sync(config: Config, *, force: bool = False) -> SyncResult:
    source = Path(config.source).expanduser().resolve()
    output = Path(config.output).expanduser().resolve()
    if source == output:
        raise ValueError("source and output must be different")
    original = source.read_bytes()
    existing = output.read_bytes() if output.exists() else None
    snapshot = _snapshot_parts(existing) if existing is not None else None
    managed = snapshot is not None
    if existing is not None and not managed and not force:
        raise PermissionError("output exists but is not an AIsteno-managed file; use --force to replace it")
    if (
        existing is not None
        and snapshot is not None
        and snapshot[0] == _digest(original)
        and snapshot[1] == _digest(snapshot[2])
    ):
        return SyncResult(False, source, output, None, _digest(original), _digest(existing), 0.0)
    result = pack(original.decode("utf-8"))
    body = result.text.encode("utf-8")
    payload = (
        f"AISTENO-SYNC/v1\nsource-sha256:{_digest(original)}\n"
        f"packed-sha256:{_digest(body)}\n"
    ).encode("ascii") + body
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
