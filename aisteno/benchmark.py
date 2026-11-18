"""Reproducible memory-packing benchmark with real tokenizer adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
from typing import Callable, Iterable

from .pack import pack


@dataclass(frozen=True)
class Question:
    question: str
    expected: tuple[str, ...]
    forbidden: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    tokens: int
    answered: int
    total_questions: int
    accuracy: float
    missed_facts: tuple[str, ...] = ()
    forbidden_matches: tuple[str, ...] = ()
    token_savings_vs_original: int = 0
    methodology: str = "deterministic lexical fact checks; not semantic model evaluation"


def _tokenizer(name: str) -> Callable[[str], int]:
    if name == "tiktoken":
        module = importlib.import_module("tiktoken")
        try:
            encoder = module.get_encoding("cl100k_base")
        except Exception as exc:
            raise RuntimeError("tiktoken vocabulary is unavailable; install/cache it before benchmarking") from exc
        return lambda text: len(encoder.encode(text))
    if name == "transformers":
        module = importlib.import_module("transformers")
        try:
            tokenizer = module.AutoTokenizer.from_pretrained("gpt2", local_files_only=True)
        except Exception as exc:
            raise RuntimeError("transformers tokenizer is unavailable locally; cache gpt2 before benchmarking") from exc
        return lambda text: len(tokenizer.encode(text, add_special_tokens=False))
    raise ValueError(f"unsupported tokenizer: {name}")


def _structured_summary(text: str) -> str:
    lines = [line.strip(" -*") for line in text.splitlines() if line.strip()]
    return "\n".join(sorted(dict.fromkeys(lines))) + ("\n" if lines else "")


def answer_questions(memory: str, questions: Iterable[Question]) -> int:
    return sum(1 for question in questions if evaluate_question(memory, question)[0])


def evaluate_question(memory: str, question: Question) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    folded = memory.casefold()
    missed = tuple(expected for expected in question.expected if expected.casefold() not in folded)
    forbidden = tuple(value for value in question.forbidden if value.casefold() in folded)
    return not missed and not forbidden, missed, forbidden


def benchmark(text: str, questions: Iterable[Question], tokenizer: str = "tiktoken") -> tuple[BenchmarkResult, ...]:
    count = _tokenizer(tokenizer)
    questions = tuple(questions)
    candidates = (
        ("original", text),
        ("aisteno", pack(text).text),
        ("structured-summary", _structured_summary(text)),
    )
    return tuple(
        _result(name, memory, questions, count, count(text))
        for name, memory in candidates
    )


def _result(name, memory, questions, count, original_tokens) -> BenchmarkResult:
    checks = tuple(evaluate_question(memory, question) for question in questions)
    missed = tuple(item for _, missing, _ in checks for item in missing)
    forbidden = tuple(item for _, _, items in checks for item in items)
    answered = sum(passed for passed, _, _ in checks)
    tokens = count(memory)
    return BenchmarkResult(
        name,
        tokens,
        answered,
        len(questions),
        answered / len(questions) if questions else 1.0,
        missed,
        forbidden,
        original_tokens - tokens,
    )


def results_to_dict(results: Iterable[BenchmarkResult]) -> list[dict[str, object]]:
    return [asdict(item) for item in results]
