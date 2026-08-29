"""Extension interfaces for sites and notification channels."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from checkin_tools.models import CheckinResult, RunReport


class Checker(ABC):
    site: str
    display_name: str

    @property
    @abstractmethod
    def accounts(self) -> Sequence[Any]:
        """Return configured accounts without exposing them in logs."""

    @abstractmethod
    def check(self, account: Any, account_label: str) -> CheckinResult:
        """Run one isolated account check-in."""


class Notifier(ABC):
    channel: str

    @abstractmethod
    def send(self, report: RunReport) -> None:
        """Send exactly one summary or raise a sanitized exception."""
