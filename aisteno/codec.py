"""Reversible AIsteno v0.1 encoder and decoder."""

from __future__ import annotations

import re

from .dictionary import BODY_MARKER, HEADER, LEGEND, SUBSTITUTIONS


class FormatError(ValueError):
    """Raised when input is not a supported AIsteno document."""


# These patterns protect exact evidence-like spans while allowing ordinary
# prose on the same line to be compressed. Conservative whole-line rules below
# protect commands, errors, and legal/forensic facts whose boundaries are hard
# to infer safely.
_PROTECTED_SPAN = re.compile(
    r"(?:"
    r"(?<!\w)(?:[A-Za-z]:[\\/]|/|\./|\.\./)[^\s<>\"'`]+"  # paths
    r"|\b(?:sha(?:1|224|256|384|512)|md5):?[0-9a-fA-F]{16,}\b"  # hashes
    r"|\b[0-9a-fA-F]{32,128}\b"  # bare hashes
    r"|\b(?:case|docket)\s*(?:no\.?|number|#)?\s*[:#-]?\s*[A-Z0-9][A-Z0-9._/-]*"  # cases
    r"|\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"  # ISO dates
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b"
    r")",
    re.IGNORECASE,
)

_PROTECTED_LINE = re.compile(
    r"^\s*(?:"
    r"[$#>]\s*\S"  # shell/prompt command
    r"|(?:command|cmd|error|exception|traceback|device|model|case|docket|legal|forensic|evidence)\s*[:#=-]"
    r"|(?:python|python3|bash|sh|zsh|git|cd|cp|mv|rm|mkdir|sudo|curl|wget|pip|npm|docker)\s+"
    r")",
    re.IGNORECASE,
)


def _is_boundary(text: str, start: int, end: int, value: str) -> bool:
    """Require word boundaries when a substitution starts/ends alphanumeric."""
    before_ok = not value[0].isalnum() or start == 0 or not text[start - 1].isalnum()
    after_ok = not value[-1].isalnum() or end == len(text) or not text[end].isalnum()
    return before_ok and after_ok


def _match_at(text: str, pos: int, values: tuple[str, ...]) -> str | None:
    for value in values:
        if text.startswith(value, pos) and _is_boundary(text, pos, pos + len(value), value):
            return value
    return None


def _encode_plain(text: str) -> str:
    phrases = tuple(item.phrase for item in SUBSTITUTIONS)
    shorthands = tuple(sorted({item.shorthand for item in SUBSTITUTIONS}, key=len, reverse=True))
    by_phrase = {item.phrase: item.shorthand for item in SUBSTITUTIONS}
    output: list[str] = []
    pos = 0
    while pos < len(text):
        phrase = _match_at(text, pos, phrases)
        if phrase is not None:
            output.append(by_phrase[phrase])
            pos += len(phrase)
            continue
        shorthand = _match_at(text, pos, shorthands)
        if shorthand is not None:
            output.append("~" + shorthand)
            pos += len(shorthand)
            continue
        if text[pos] == "~":
            output.append("~~")
        else:
            output.append(text[pos])
        pos += 1
    return "".join(output)


def _escape_only(text: str) -> str:
    """Escape decoder-sensitive literals without compressing protected text."""
    shorthands = tuple(sorted({item.shorthand for item in SUBSTITUTIONS}, key=len, reverse=True))
    output: list[str] = []
    pos = 0
    while pos < len(text):
        shorthand = _match_at(text, pos, shorthands)
        if shorthand is not None:
            output.append("~" + shorthand)
            pos += len(shorthand)
            continue
        output.append("~~" if text[pos] == "~" else text[pos])
        pos += 1
    return "".join(output)


def _encode_line(line: str) -> str:
    if _PROTECTED_LINE.match(line):
        return _escape_only(line)
    output: list[str] = []
    last = 0
    for match in _PROTECTED_SPAN.finditer(line):
        output.append(_encode_plain(line[last : match.start()]))
        output.append(_escape_only(match.group(0)))
        last = match.end()
    output.append(_encode_plain(line[last:]))
    return "".join(output)


def encode(text: str) -> str:
    """Return an AIsteno v0.1 document encoding *text*."""
    body = "".join(_encode_line(line) for line in text.splitlines(keepends=True))
    return HEADER + body


def _decode_body(body: str) -> str:
    shorthands = tuple(sorted({item.shorthand for item in SUBSTITUTIONS}, key=len, reverse=True))
    by_shorthand: dict[str, str] = {}
    for item in SUBSTITUTIONS:
        if item.shorthand in by_shorthand:
            raise RuntimeError(f"non-reversible duplicate shorthand: {item.shorthand}")
        by_shorthand[item.shorthand] = item.phrase

    output: list[str] = []
    pos = 0
    while pos < len(body):
        if body[pos] == "~":
            if pos + 1 < len(body) and body[pos + 1] == "~":
                output.append("~")
                pos += 2
                continue
            literal = _match_at(body, pos + 1, shorthands)
            if literal is None:
                raise FormatError(f"invalid escape at body character {pos}")
            output.append(literal)
            pos += len(literal) + 1
            continue
        shorthand = _match_at(body, pos, shorthands)
        if shorthand is not None:
            output.append(by_shorthand[shorthand])
            pos += len(shorthand)
            continue
        output.append(body[pos])
        pos += 1
    return "".join(output)


def decode(document: str) -> str:
    """Decode a complete AIsteno v0.1 document."""
    if not document.startswith(LEGEND):
        raise FormatError("missing or unsupported AIsteno header")
    marker_at = len(LEGEND)
    if document[marker_at : marker_at + len(BODY_MARKER)] != BODY_MARKER:
        raise FormatError("missing AIsteno BODY marker")
    return _decode_body(document[marker_at + len(BODY_MARKER) :])


def roundtrip_matches(text: str) -> bool:
    return decode(encode(text)) == text
