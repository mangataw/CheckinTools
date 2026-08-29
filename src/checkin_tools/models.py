"""Shared result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


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


@dataclass(frozen=True, slots=True)
class NotificationResult:
    channel: str
    success: bool
    summary: str


@dataclass(slots=True)
class RunReport:
    results: list[CheckinResult] = field(default_factory=list)
    notifications: list[NotificationResult] = field(default_factory=list)

    def count(self, status: ResultStatus) -> int:
        return sum(result.status is status for result in self.results)

    @property
    def exit_code(self) -> int:
        if not self.results:
            return 2
        if self.count(ResultStatus.FAILED) or any(
            not notification.success for notification in self.notifications
        ):
            return 1
        return 0

