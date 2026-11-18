"""Versioned schema and extensible transformations for structured memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Callable, Mapping


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Transformation:
    name: str
    version: str
    apply: Callable[[str], str]


@dataclass(frozen=True)
class MemorySchema:
    version: str
    transformations: tuple[Transformation, ...]

    def transform(self, value: str) -> str:
        for transformation in self.transformations:
            value = transformation.apply(value)
        return value


def _strip_filler(value: str) -> str:
    return re.sub(
        r"\b(?:remember that|please remember that|currently|the user prefers|user prefers)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .;,:")


DEFAULT_SCHEMA = MemorySchema(
    SCHEMA_VERSION,
    (
        Transformation("strip-filler", "1.0", _strip_filler),
        Transformation("normalize-whitespace", "1.0", _normalize_whitespace),
    ),
)


def utc_timestamp(value: datetime | None = None) -> str:
    """Return a stable ISO-8601 timestamp for fact metadata."""
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def schema_metadata(schema: MemorySchema = DEFAULT_SCHEMA) -> Mapping[str, object]:
    return {
        "version": schema.version,
        "transformations": [
            {"name": item.name, "version": item.version} for item in schema.transformations
        ],
    }
