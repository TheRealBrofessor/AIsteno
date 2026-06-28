"""Command-line interface for AIsteno."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codec import FormatError, decode, encode, roundtrip_matches
from .pack import pack
from .report import calculate_pack_stats, calculate_stats, format_pack_stats, format_stats
from .secrets import format_secret_scan, scan_secrets


def _read(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def _safe_write(input_path: Path, output_path: Path, content: str, *, force: bool = False) -> None:
    input_resolved = input_path.resolve()
    output_resolved = output_path.resolve()
    if input_resolved == output_resolved:
        raise ValueError("refusing to overwrite the input file")
    if output_path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing output: {output_path}")
    mode = "w" if force else "x"
    with output_path.open(mode, encoding="utf-8", newline="") as stream:
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing OUTPUT; requires --apply",
    )


def _add_pack_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("pack")
    parser.add_argument("input", type=Path, metavar="INPUT")
    parser.add_argument("--out", type=Path, metavar="OUTPUT")
    parser.add_argument("--apply", action="store_true", help="write OUTPUT (default: preview only)")
    parser.add_argument("--force", action="store_true", help="overwrite OUTPUT; requires --apply")
    parser.add_argument("--legend", action="store_true", help="include the compact tag legend")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aisteno")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_transform_parser(subparsers, "encode")
    _add_transform_parser(subparsers, "decode")
    _add_pack_parser(subparsers)
    for name in ("preview", "stats", "roundtrip"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("input", type=Path, metavar="INPUT")
    pack_preview = subparsers.add_parser("pack-preview")
    pack_preview.add_argument("input", type=Path, metavar="INPUT")
    pack_preview.add_argument("--legend", action="store_true", help="include the compact tag legend")
    pack_stats = subparsers.add_parser("pack-stats")
    pack_stats.add_argument("input", type=Path, metavar="INPUT")
    secret_scan = subparsers.add_parser("secret-scan")
    secret_scan.add_argument("input", type=Path, metavar="INPUT")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = _read(args.input)
        if getattr(args, "force", False) and not getattr(args, "apply", False):
            raise ValueError("--force requires --apply")
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
        elif args.command == "pack-stats":
            print(format_pack_stats(calculate_pack_stats(text)))
            return 0
        elif args.command == "secret-scan":
            print(format_secret_scan(scan_secrets(text)))
            return 0
        elif args.command == "pack-preview":
            sys.stdout.write(pack(text, legend=args.legend).text)
            return 0
        elif args.command == "pack":
            result = pack(text, legend=args.legend).text
            if args.out is None:
                sys.stdout.write(result)
                return 0
        else:
            matches = roundtrip_matches(text)
            print("roundtrip: PASS" if matches else "roundtrip: FAIL")
            return 0 if matches else 1

        if args.apply:
            if args.out is None:
                raise ValueError("--apply requires --out")
            _safe_write(args.input, args.out, result, force=args.force)
            print(f"created: {args.out}")
        else:
            if args.out is not None:
                print(f"DRY RUN: would create {args.out}", file=sys.stderr)
            sys.stdout.write(result)
        return 0
    except (OSError, UnicodeError, ValueError, FormatError) as exc:
        print(f"aisteno: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
