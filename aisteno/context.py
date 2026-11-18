"""Token-budget-aware selection of verified canonical facts."""

from __future__ import annotations

from .facts import CanonicalFact


def select_facts(facts: tuple[CanonicalFact, ...], budget: int, tokenizer) -> tuple[CanonicalFact, ...]:
    if budget < 0:
        raise ValueError("budget must be non-negative")
    mandatory = [fact for fact in facts if fact.domain in {"RULE", "RISK", "AGENT"}]
    optional = [fact for fact in facts if fact not in mandatory]
    selected: list[CanonicalFact] = []
    used = 0
    for fact in mandatory + optional:
        cost = tokenizer(f"{fact.key}={fact.value}")
        if used + cost > budget:
            continue
        selected.append(fact)
        used += cost
    return tuple(selected)
