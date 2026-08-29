"""Log and exception redaction helpers."""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import urlsplit, urlunsplit

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(cookie|authorization|access[_-]?token|secret|webhook)\s*[:=]\s*[^\s,;]+"
)


def sanitize_text(value: object, secrets: tuple[str, ...] = ()) -> str:
    text = str(value)
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        text = text.replace(secret, "***")
    text = _SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=***", text)
    for candidate in re.findall(r"https://[^\s]+", text):
        parsed = urlsplit(candidate.rstrip(".,)"))
        if parsed.query:
            clean = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
            text = text.replace(candidate, clean)
    return text


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.secrets = secrets

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = sanitize_text(record.getMessage(), self.secrets)
        record.args = ()
        return True


def configure_logging(secrets: tuple[str, ...] = ()) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter(secrets))
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def register_ci_masks(secrets: tuple[str, ...]) -> None:
    if os.getenv("GITHUB_ACTIONS") == "true":
        for secret in secrets:
            if secret:
                print(f"::add-mask::{secret}")

