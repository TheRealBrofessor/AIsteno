"""Command-line interface for AIsteno."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codec import FormatError, decode, encode, roundtrip_matches
from .pack import pack
from .report import calculate_pack_stats, calculate_stats, format_pack_stats, format_stats
from .secrets import format_secret_scan, scan_secrets
from .integrations import pack_json
from .config import Config, load_config, validate_config
from .setup import setup
from .sync import restore, sync, watch
from .dashboard import serve as serve_dashboard
from .mcp_server import serve as serve_mcp
from . import __version__


def _read(path: Path) -> str:
    if str(path) == "-":
        return sys.stdin.read()
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
    parser.add_argument("--json", action="store_true", help="emit canonical facts as JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aisteno")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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
    pack_json_parser = subparsers.add_parser("pack-json")
    pack_json_parser.add_argument("input", type=Path, metavar="INPUT")
    setup_parser = subparsers.add_parser("setup", help="discover and approve an agent memory source")
    setup_parser.add_argument("--source", type=Path)
    setup_parser.add_argument("--output", type=Path)
    setup_parser.add_argument("--yes", action="store_true", help="approve the displayed source and output")
    sync_parser = subparsers.add_parser("sync", help="compile configured memory safely")
    sync_parser.add_argument("--force", action="store_true")
    subparsers.add_parser("validate", help="validate the configured source and output")
    watch_parser = subparsers.add_parser("watch", help="automatically sync when source memory changes")
    watch_parser.add_argument("--interval", type=float, default=2.0)
    watch_parser.add_argument("--once", action="store_true")
    restore_parser = subparsers.add_parser("restore", help="restore a named backup")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("--output", type=Path)
    dashboard_parser = subparsers.add_parser("dashboard", help="serve the local dashboard")
    dashboard_parser.add_argument("--host", default="127.0.0.1")
    dashboard_parser.add_argument("--port", type=int, default=8765)
    mcp_parser = subparsers.add_parser("mcp", help="run the MCP-compatible stdio bridge")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = _read(args.input) if hasattr(args, "input") else ""
        if (
            getattr(args, "force", False)
            and args.command in {"encode", "decode", "pack"}
            and not getattr(args, "apply", False)
        ):
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
        elif args.command == "pack-json":
            sys.stdout.write(pack_json(text))
            return 0
        elif args.command == "setup":
            config = setup(
                assume_yes=args.yes,
                source=args.source,
                output=args.output,
            )
            print(f"configured: {config.source} -> {config.output}")
            return 0
        elif args.command == "sync":
            result = sync(load_config(), force=args.force)
            print(f"{'updated' if result.changed else 'unchanged'}: {result.output}")
            return 0
        elif args.command == "validate":
            validate_config(load_config())
            print("configuration: valid")
            return 0
        elif args.command == "watch":
            for result in watch(load_config(), interval=args.interval, once=args.once):
                print(f"{'updated' if result.changed else 'unchanged'}: {result.output}", flush=True)
            return 0
        elif args.command == "restore":
            config = load_config()
            restore(args.backup, args.output or Path(config.output))
            print(f"restored: {args.output or config.output}")
            return 0
        elif args.command == "dashboard":
            serve_dashboard(args.host, args.port).serve_forever()
            return 0
        elif args.command == "mcp":
            serve_mcp()
            return 0
        elif args.command == "pack-preview":
            sys.stdout.write(pack(text, legend=args.legend).text)
            return 0
        elif args.command == "pack":
            result = pack_json(text) if args.json else pack(text, legend=args.legend).text
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
