"""Local configuration for AIsteno product integrations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import os
import tempfile


@dataclass(frozen=True)
class Config:
    source: str
    output: str
    agent: str = "hermes"
    token_budget: int | None = None
    backup_dir: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Config":
        return cls(
            source=str(data["source"]),
            output=str(data["output"]),
            agent=str(data.get("agent", "hermes")),
            token_budget=int(data["token_budget"]) if data.get("token_budget") is not None else None,
            backup_dir=str(data["backup_dir"]) if data.get("backup_dir") else None,
        )


def config_path() -> Path:
    return Path(os.environ.get("AISTENO_CONFIG", "~/.config/aisteno/config.json")).expanduser()


def load_config(path: Path | None = None) -> Config:
    target = path or config_path()
    return Config.from_dict(json.loads(target.read_text(encoding="utf-8")))


def save_config(config: Config, path: Path | None = None) -> Path:
    target = (path or config_path()).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=target.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(asdict(config), stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return target


def validate_config(config: Config) -> None:
    source = Path(config.source).expanduser().resolve()
    output = Path(config.output).expanduser().resolve()
    if source == output:
        raise ValueError("configured source and output must be different")
    if not source.is_file():
        raise FileNotFoundError(f"configured source does not exist: {source}")
    if config.token_budget is not None and config.token_budget < 0:
        raise ValueError("token_budget must be non-negative")
