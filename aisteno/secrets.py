"""Fail-closed secret detection for AIsteno pack mode.

The scanner combines established ``detect-secrets`` when installed with
format-aware detectors. It never stores or prints the matched value.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


class SecretClassificationError(ValueError):
    """Raised when a possible credential cannot be safely classified."""


@dataclass(frozen=True)
class SecretFinding:
    line_number: int
    secret_type: str
    redacted_preview: str


@dataclass(frozen=True)
class SecretScan:
    redacted_text: str
    findings: tuple[SecretFinding, ...]
    ambiguous: tuple[int, ...] = ()

    @property
    def safe(self) -> bool:
        return not self.ambiguous


_LABEL = (
    r"sudo\s+password|bridge\s+password|login\s+credential|"
    r"access[_ -]?token|api[_ -]?key|client[_ -]?secret|"
    r"aws[_ -]?secret[_ -]?access[_ -]?key|private[_ -]?key|"
    r"password|passwd|pw|sudo|token|secret|credential"
)
_LABELED = re.compile(
    rf"(?P<label>\b(?:{_LABEL})\b)\s*(?:=|:|\bis\b)\s*"
    r"(?P<value>\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,;]+)",
    re.IGNORECASE,
)
_BARE = re.compile(
    rf"^\s*(?:[-*+]\s+)?(?P<label>{_LABEL})\s+"
    r"(?P<value>\"[^\"\r\n]+\"|'[^'\r\n]+'|\S+)\s*$",
    re.IGNORECASE,
)
_PASSWORD_LIKE = re.compile(
    r"(?<![\w@])(?=[^\s,;]{10,})(?=[^\s,;]*[a-z])(?=[^\s,;]*[A-Z])"
    r"(?=[^\s,;]*\d)(?=[^\s,;]*[!$%^&*])[^\s,;]+"
)
_FORMATS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{12,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
_AMBIGUOUS = re.compile(r"(?<![\w@])[A-Za-z0-9+/=_-]{40,}(?!\w)")
_ENV_SECRET = re.compile(
    r"\b(?:AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|GITHUB_TOKEN|"
    r"OPENAI_API_KEY|ANTHROPIC_API_KEY|DATABASE_URL|CLIENT_SECRET)\s*=\s*"
    r"(?P<value>\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,;]+)",
    re.IGNORECASE,
)
_JSON_SECRET = re.compile(
    r"\"(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|private[_-]?key)\""
    r"\s*:\s*\"(?P<value>[^\"]+)\"",
    re.IGNORECASE,
)


def _secret_type(label: str) -> str:
    normalized = re.sub(r"[ _-]+", " ", label.casefold()).strip()
    if normalized.startswith("sudo"):
        return "sudo"
    if normalized == "api key":
        return "api_key"
    if "private" in normalized:
        return "private_key"
    if "client secret" in normalized:
        return "credential"
    if "token" in normalized:
        return "token"
    if normalized == "secret":
        return "secret"
    return "password"


def _preview(line: str, limit: int = 180) -> str:
    line = re.sub(r"\s+", " ", line.strip())
    return line if len(line) <= limit else line[: limit - 1] + "…"


def _external_findings(text: str) -> tuple[tuple[int, str, str], ...]:
    try:
        from detect_secrets.settings import transient_settings
        from detect_secrets.core.plugins.util import get_mapping_from_secret_type_to_class
    except ImportError:
        return ()
    findings: list[tuple[int, str, str]] = []
    plugin_names = [
        plugin.__name__
        for name, plugin in get_mapping_from_secret_type_to_class().items()
        if name not in {"Base64 High Entropy String", "Hex High Entropy String", "Public IP (ipv4)"}
    ]
    with transient_settings({"plugins_used": [{"name": name} for name in plugin_names]}):
        for line_number, line in enumerate(text.splitlines(), start=1):
            from detect_secrets.core.scan import scan_line
            for finding in scan_line(line):
                value = str(getattr(finding, "secret_value", ""))
                kind = str(getattr(finding, "type", "detector")).casefold().replace(" ", "_")
                if value:
                    findings.append((line_number, kind, value))
    return tuple(findings)


def scan_secrets(text: str) -> SecretScan:
    """Return redacted text; ``ambiguous`` makes pack mode refuse to continue."""
    findings: list[tuple[int, str, str]] = []
    ambiguous: set[int] = set()
    redacted_lines: list[str] = []
    external = _external_findings(text)
    external_by_line: dict[int, list[tuple[str, str]]] = {}
    for line_number, kind, value in external:
        external_by_line.setdefault(line_number, []).append((kind, value))
    private_active = False
    for line_number, original in enumerate(text.splitlines(keepends=True), start=1):
        newline = ""
        content = original
        if content.endswith("\r\n"):
            content, newline = content[:-2], "\r\n"
        elif content.endswith(("\n", "\r")):
            content, newline = content[:-1], content[-1]
        private_header = re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", content)
        if private_active or private_header:
            marker = "SECRET{type=private_key;stored=no}"
            if private_header:
                content = content[:private_header.start()] + marker
            else:
                content = marker
            private_active = "-----END " not in original
            findings.append((line_number, "private_key", content))
            redacted_lines.append(content + newline)
            continue
        matches: list[tuple[int, int, str]] = []
        for match in _LABELED.finditer(content):
            matches.append((*match.span("value"), _secret_type(match.group("label"))))
        bare = _BARE.match(content)
        if bare:
            matches.append((*bare.span("value"), _secret_type(bare.group("label"))))
        for secret_type, pattern in _FORMATS:
            matches.extend((match.start(), match.end(), secret_type) for match in pattern.finditer(content))
        for match in _ENV_SECRET.finditer(content):
            matches.append((*match.span("value"), "environment_secret"))
        for match in _JSON_SECRET.finditer(content):
            matches.append((*match.span("value"), "json_credential"))
        labeled_spans = [(start, end) for start, end, _ in matches]
        bare_span = bare.span() if bare else None
        for match in _PASSWORD_LIKE.finditer(content):
            if any(match.start() < end and match.end() > start for start, end in labeled_spans):
                continue
            matches.append((*match.span(), "password"))
        if bare_span:
            matches = [(bare_span[0], bare_span[1], _secret_type(bare.group("label")))]
        for detector_type, detector_value in external_by_line.get(line_number, []):
            if detector_value and detector_value in content:
                start = content.find(detector_value)
                matches.append((start, start + len(detector_value), f"detector_{detector_type}"))
            else:
                ambiguous.add(line_number)
        selected: list[tuple[int, int, str]] = []
        for start, end, kind in sorted(matches, key=lambda item: (item[0], -(item[1] - item[0]))):
            if any(start < used_end and end > used_start for used_start, used_end, _ in selected):
                continue
            selected.append((start, end, kind))
        for start, end, kind in reversed(selected):
            marker = f"SECRET{{type={kind};stored=no}}"
            content = content[:start] + marker + content[end:]
            findings.append((line_number, kind, content))
        path_like = re.search(r"(?:^|[\s=:])(?:[A-Za-z]:[\\/]|/|~/)[^\s]+", content)
        hash_like = re.search(r"\b(?:sha(?:1|224|256|384|512)|md5):?[0-9a-f]{32,}\b", content, re.I)
        if not matches and _AMBIGUOUS.search(content) and not path_like and not hash_like:
            ambiguous.add(line_number)
        redacted_lines.append(content + newline)
    if private_active:
        ambiguous.add(max(1, len(text.splitlines())))
    result = "".join(redacted_lines)
    return SecretScan(
        result,
        tuple(SecretFinding(line, kind, _preview(re.sub(r"SECRET\{type=[^}]+;stored=no\}", f"{kind}=[REDACTED]", line_text))) for line, kind, line_text in findings),
        tuple(sorted(ambiguous)),
    )


def ensure_safe(scan: SecretScan) -> None:
    if scan.ambiguous:
        lines = ", ".join(str(item) for item in scan.ambiguous)
        raise SecretClassificationError(f"unclassified sensitive data on line(s): {lines}")


def format_secret_scan(scan: SecretScan) -> str:
    lines = [f"possible secrets: {len(scan.findings)}"]
    lines.extend(
        f"line {finding.line_number}: type={finding.secret_type} preview={finding.redacted_preview}"
        for finding in scan.findings
    )
    if scan.ambiguous:
        lines.append("blocked: unclassified sensitive data on line(s) " + ", ".join(map(str, scan.ambiguous)))
    return "\n".join(lines)
