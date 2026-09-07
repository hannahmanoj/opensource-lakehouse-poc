import re


SECRET_PATTERNS = [
    re.compile(
        r"(?i)(password|token|secret|api[_-]?key)"
        r"(\s*[=:]\s*)([^\s,;]+)"
    ),
    re.compile(
        r"(?i)(authorization\s*:\s*bearer\s+)([^\s]+)"
    ),
]


def redact_secrets(text: str) -> str:
    redacted = text

    for pattern in SECRET_PATTERNS:
        if pattern.groups == 3:
            redacted = pattern.sub(
                r"\1\2[REDACTED]",
                redacted,
            )
        else:
            redacted = pattern.sub(
                r"\1[REDACTED]",
                redacted,
            )

    return redacted


def safe_log(text: str, max_bytes: int) -> dict:
    raw = text.encode("utf-8")
    truncated = len(raw) > max_bytes

    if truncated:
        text = raw[:max_bytes].decode(
            "utf-8",
            errors="ignore",
        )
        text += "\n[TRUNCATED]"

    return {
        "log": redact_secrets(text),
        "truncated": truncated,
        "max_bytes": max_bytes,
    }