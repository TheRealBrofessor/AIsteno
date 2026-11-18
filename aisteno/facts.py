"""Canonical facts with provenance, conflicts, timestamps, and supersession."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from typing import Iterable

from .schema import DEFAULT_SCHEMA, MemorySchema, utc_timestamp


@dataclass(frozen=True)
class Provenance:
    source: str
    line: int
    excerpt: str


@dataclass(frozen=True)
class CanonicalFact:
    domain: str
    key: str
    value: str
    observed_at: str
    provenance: tuple[Provenance, ...] = ()
    conflicts: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()

    @property
    def identity(self) -> str:
        return f"{self.domain}:{self.key}"

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["provenance"] = [asdict(item) for item in self.provenance]
        return result


_TIMESTAMP = re.compile(
    r"\b(?:as of|updated?|observed|effective)\s*[:=]?\s*"
    r"(?P<value>\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?)",
    re.IGNORECASE,
)
_SUPERSEDES = re.compile(r"\b(?:supersedes?|replaces?|instead of)\s+(?P<value>[^.;]+)", re.IGNORECASE)


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _same_canonical_value(left: str, right: str) -> bool:
    if _normalized(left) == _normalized(right):
        return True
    # Structured alternatives such as ``concise/direct`` intentionally
    # subsume their individual components; arbitrary substrings do not.
    for broader, narrower in ((left, right), (right, left)):
        parts = {_normalized(item) for item in broader.split("/") if item}
        if len(parts) > 1 and _normalized(narrower) in parts:
            return True
    return False


def canonicalize(
    records: Iterable[tuple[str, str, str, int]],
    *,
    source: str = "stdin",
    schema: MemorySchema = DEFAULT_SCHEMA,
    observed_at: str | None = None,
) -> tuple[CanonicalFact, ...]:
    """Build facts without substring-based merging.

    Records are ``(domain, key, value, line)``. Equal normalized identities and
    values merge; differing values remain explicit conflicts.
    """
    grouped: dict[str, list[CanonicalFact]] = {}
    for domain, key, value, line in records:
        value = schema.transform(value)
        if not value:
            continue
        timestamp = _TIMESTAMP.search(value)
        fact_time = timestamp.group("value") if timestamp else (observed_at or utc_timestamp())
        superseded = _SUPERSEDES.search(value)
        supersedes = (superseded.group("value").strip(),) if superseded else ()
        clean_value = _SUPERSEDES.sub("", value).strip(" .;,:")
        candidate = CanonicalFact(
            domain=domain,
            key=key,
            value=clean_value,
            observed_at=fact_time,
            provenance=(Provenance(source, line, value[:240]),),
            supersedes=supersedes,
        )
        identity = candidate.identity
        existing = grouped.setdefault(identity, [])
        same = next((item for item in existing if _same_canonical_value(item.value, candidate.value)), None)
        if same:
            value = same.value if len(same.value) >= len(candidate.value) else candidate.value
            existing[existing.index(same)] = CanonicalFact(
                same.domain,
                same.key,
                value,
                max(same.observed_at, candidate.observed_at),
                same.provenance + candidate.provenance,
                same.conflicts,
                tuple(dict.fromkeys(same.supersedes + candidate.supersedes)),
            )
        else:
            existing.append(candidate)

    result: list[CanonicalFact] = []
    for values in grouped.values():
        all_values = tuple(item.value for item in values)
        for item in values:
            conflicts = tuple(value for value in all_values if not _same_canonical_value(value, item.value))
            result.append(
                CanonicalFact(
                    item.domain,
                    item.key,
                    item.value,
                    item.observed_at,
                    item.provenance,
                    conflicts,
                    item.supersedes,
                )
            )
    return tuple(result)


def facts_to_json(facts: Iterable[CanonicalFact]) -> str:
    return json.dumps([fact.as_dict() for fact in facts], indent=2, sort_keys=True) + "\n"
