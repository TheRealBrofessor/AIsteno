"""Run the tokenizer benchmark: python benchmarks/run.py [tiktoken|transformers]."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aisteno.benchmark import Question, benchmark, results_to_dict


def main() -> int:
    corpus = json.loads((Path(__file__).with_name("corpus.json")).read_text(encoding="utf-8"))
    questions = tuple(Question(item["question"], tuple(item["expected"])) for item in corpus["questions"])
    tokenizer = sys.argv[1] if len(sys.argv) > 1 else "tiktoken"
    try:
        results = benchmark(corpus["memory"], questions, tokenizer)
    except ImportError as exc:
        print(f"missing tokenizer dependency: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(results_to_dict(results), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
