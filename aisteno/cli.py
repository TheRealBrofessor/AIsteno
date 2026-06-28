"""Command-line interface for AIsteno."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codec import FormatError, decode, encode, roundtrip_matches
from .report import calculate_stats, format_stats


def _read(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def _safe_write(input_path: Path, output_path: Path, content: str) -> None:
    input_resolved = input_path.resolve()
    output_resolved = output_path.resolve()
    if input_resolved == output_resolved:
        raise ValueError("refusing to overwrite the input file")
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_path}")
    with output_path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(content)


def _add_transform_parser(subparsers: argparse._SubParsersAction, name: str) -> None:
    parser = subparsers.add_parser(name)
    parser.add_argument("input", type=Path, metavar="INPUT")
    parser.add_argument("--out", required=True, type=Path, metavar="OUTPUT")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create OUTPUT (default: preview only)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aisteno")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_transform_parser(subparsers, "encode")
    _add_transform_parser(subparsers, "decode")
    for name in ("preview", "stats", "roundtrip"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("input", type=Path, metavar="INPUT")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = _read(args.input)
        if args.command == "encode":
            result = encode(text)
        elif args.command == "decode":
            result = decode(text)
        elif args.command == "preview":
            sys.stdout.write(encode(text))
            return 0
        elif args.command == "stats":
            print(format_stats(calculate_stats(text)))
            return 0
        else:
            matches = roundtrip_matches(text)
            print("roundtrip: PASS" if matches else "roundtrip: FAIL")
            return 0 if matches else 1

        if args.apply:
            _safe_write(args.input, args.out, result)
            print(f"created: {args.out}")
        else:
            print(f"DRY RUN: would create {args.out}", file=sys.stderr)
            sys.stdout.write(result)
        return 0
    except (OSError, UnicodeError, ValueError, FormatError) as exc:
        print(f"aisteno: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
