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


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    tokens: int
    answered: int
    total_questions: int
    accuracy: float


def _tokenizer(name: str) -> Callable[[str], int]:
    if name == "tiktoken":
        module = importlib.import_module("tiktoken")
        encoder = module.get_encoding("cl100k_base")
        return lambda text: len(encoder.encode(text))
    if name == "transformers":
        module = importlib.import_module("transformers")
        tokenizer = module.AutoTokenizer.from_pretrained("gpt2")
        return lambda text: len(tokenizer.encode(text, add_special_tokens=False))
    raise ValueError(f"unsupported tokenizer: {name}")


def _structured_summary(text: str) -> str:
    lines = [line.strip(" -*") for line in text.splitlines() if line.strip()]
    return "\n".join(sorted(dict.fromkeys(lines))) + ("\n" if lines else "")


def answer_questions(memory: str, questions: Iterable[Question]) -> int:
    folded = memory.casefold()
    return sum(
        1
        for question in questions
        if all(expected.casefold() in folded for expected in question.expected)
    )


def benchmark(text: str, questions: Iterable[Question], tokenizer: str = "tiktoken") -> tuple[BenchmarkResult, ...]:
    count = _tokenizer(tokenizer)
    questions = tuple(questions)
    candidates = (
        ("original", text),
        ("aisteno", pack(text).text),
        ("structured-summary", _structured_summary(text)),
    )
    return tuple(
        BenchmarkResult(
            name,
            count(memory),
            answer_questions(memory, questions),
            len(questions),
            answer_questions(memory, questions) / len(questions) if questions else 1.0,
        )
        for name, memory in candidates
    )


def results_to_dict(results: Iterable[BenchmarkResult]) -> list[dict[str, object]]:
    return [asdict(item) for item in results]
