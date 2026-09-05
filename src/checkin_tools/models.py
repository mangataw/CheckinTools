"""Shared result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - exercised on Python 3.10
    class StrEnum(str, Enum):
        """Python 3.10 compatibility for enum.StrEnum."""


class ResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    ALREADY_DONE = "ALREADY_DONE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CheckinResult:
    site: str
    account: str
    status: ResultStatus
    summary: str
    duration_seconds: float
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class NotificationResult:
    channel: str
    success: bool
    summary: str


@dataclass(slots=True)
class RunReport:
    results: list[CheckinResult] = field(default_factory=list)
    notifications: list[NotificationResult] = field(default_factory=list)
    skipped_accounts: int = 0

    def count(self, status: ResultStatus) -> int:
        return sum(result.status is status for result in self.results)

    @property
    def exit_code(self) -> int:
        if not self.results and self.skipped_accounts:
            return 0
        if not self.results:
            return 2
        if self.count(ResultStatus.FAILED) or any(
            not notification.success for notification in self.notifications
        ):
            return 1
        return 0
