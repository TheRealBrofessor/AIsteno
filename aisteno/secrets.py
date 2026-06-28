"""Non-leaking secret detection for AIsteno pack mode."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SecretFinding:
    """Safe scan result: intentionally stores no original secret value."""

    line_number: int
    secret_type: str
    redacted_preview: str


@dataclass(frozen=True)
class SecretScan:
    redacted_text: str
    findings: tuple[SecretFinding, ...]


_LABELED_SECRET = re.compile(
    r"(?P<label>\b(?:"
    r"sudo\s+password|bridge\s+password|login\s+credential|"
    r"access[_ -]?token|api[_ -]?key|password|passwd|pw|sudo|token|secret"
    r")\b)"
    r"\s*(?:=|:|\bis\b)\s*"
    r"(?P<value>\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,;]+)",
    re.IGNORECASE,
)

# Conservative unlabeled credential heuristic: mixed case + digit + a strong
# password punctuation character. It avoids emails, hashes, case numbers, and
# ordinary device serials while catching common pasted passwords.
_PASSWORD_LIKE = re.compile(
    r"(?<![\w@])(?=[^\s,;]{10,})(?=[^\s,;]*[a-z])(?=[^\s,;]*[A-Z])"
    r"(?=[^\s,;]*\d)(?=[^\s,;]*[!$%^&*])[^\s,;]+"
)

_BARE_SECRET = re.compile(
    r"^\s*(?:[-*+]\s+)?(?P<label>"
    r"sudo\s+password|bridge\s+password|login\s+credential|"
    r"access[_ -]?token|api[_ -]?key|password|passwd|pw|token|secret"
    r")\s+(?P<value>\"[^\"\r\n]+\"|'[^'\r\n]+'|\S+)\s*$",
    re.IGNORECASE,
)


def _secret_type(label: str) -> str:
    normalized = re.sub(r"[ _-]+", " ", label.casefold()).strip()
    if normalized.startswith("sudo"):
        return "sudo"
    if normalized == "api key":
        return "api_key"
    if "token" in normalized:
        return "token"
    if normalized == "secret":
        return "secret"
    return "password"


def _preview(redacted_line: str, limit: int = 180) -> str:
    preview = redacted_line.strip()
    if len(preview) > limit:
        preview = preview[: limit - 1] + "…"
    return preview


def scan_secrets(text: str) -> SecretScan:
    """Return fully redacted text and findings that contain no secret values."""
    finding_metadata: list[tuple[int, str]] = []
    discovered_values: list[str] = []
    redacted_lines: list[str] = []
    lines = text.splitlines(keepends=True)

    for line_number, line in enumerate(lines, start=1):
        newline = ""
        content = line
        if content.endswith("\r\n"):
            content, newline = content[:-2], "\r\n"
        elif content.endswith(("\n", "\r")):
            content, newline = content[:-1], content[-1]

        matches: list[tuple[int, int, str, str]] = []
        occupied: list[tuple[int, int]] = []
        for match in _LABELED_SECRET.finditer(content):
            start, end = match.span()
            while end > start and content[end - 1] in ".,":
                end -= 1
            value = match.group("value").rstrip(".,")
            matches.append((start, end, _secret_type(match.group("label")), value))
            occupied.append((start, end))

        bare_match = _BARE_SECRET.match(content)
        if bare_match:
            start, end = bare_match.span()
            if not any(start < used_end and end > used_start for used_start, used_end in occupied):
                while end > start and content[end - 1] in ".,":
                    end -= 1
                value = bare_match.group("value").rstrip(".,")
                matches.append((start, end, _secret_type(bare_match.group("label")), value))
                occupied.append((start, end))

        for match in _PASSWORD_LIKE.finditer(content):
            start, end = match.span()
            while end > start and content[end - 1] in ".,":
                end -= 1
            if any(start < used_end and end > used_start for used_start, used_end in occupied):
                continue
            matches.append((start, end, "password", content[start:end]))

        matches.sort(key=lambda item: item[0])
        safe_parts: list[str] = []
        cursor = 0
        for start, end, secret_type, value in matches:
            safe_parts.append(content[cursor:start])
            safe_parts.append(f"SECRET{{type={secret_type};stored=no}}")
            cursor = end
            finding_metadata.append((line_number, secret_type))
            discovered_values.append(value)
        safe_parts.append(content[cursor:])
        safe_line = "".join(safe_parts)
        redacted_lines.append(safe_line + newline)

    # splitlines(keepends=True) returns no item for an empty input.
    redacted_text = "".join(redacted_lines)
    for value in discovered_values:
        candidates = (value, value[1:-1]) if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else (value,)
        for candidate in candidates:
            if len(candidate) >= 4:
                redacted_text = redacted_text.replace(candidate, "[REDACTED]")

    preview_lines = redacted_text.splitlines()
    findings = tuple(
        SecretFinding(
            line_number,
            secret_type,
            _preview(
                re.sub(
                    r"SECRET\{type=([a-z_]+);stored=no\}",
                    r"\1=[REDACTED]",
                    preview_lines[line_number - 1] if line_number <= len(preview_lines) else "",
                )
            ),
        )
        for line_number, secret_type in finding_metadata
    )
    return SecretScan(redacted_text, findings)


def format_secret_scan(scan: SecretScan) -> str:
    lines = [f"possible secrets: {len(scan.findings)}"]
    lines.extend(
        f"line {finding.line_number}: type={finding.secret_type} preview={finding.redacted_preview}"
        for finding in scan.findings
    )
    return "\n".join(lines)
