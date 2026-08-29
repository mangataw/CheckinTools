"""Failure-isolating execution orchestration."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable

from checkin_tools.interfaces import Checker, Notifier
from checkin_tools.models import CheckinResult, NotificationResult, ResultStatus, RunReport
from checkin_tools.registry import checker_map
from checkin_tools.security import sanitize_text

LOGGER = logging.getLogger(__name__)


class Runner:
    def __init__(self, checkers: Iterable[Checker], notifiers: Iterable[Notifier] = ()) -> None:
        self.checkers = checker_map(checkers)
        self.notifiers = list(notifiers)

    def run(self, site: str = "all", *, notify: bool = True) -> RunReport:
        selected = list(self.checkers.values()) if site == "all" else [self.checkers.get(site)]
        selected = [checker for checker in selected if checker is not None]
        report = RunReport()
        for checker in selected:
            for index, account in enumerate(checker.accounts, start=1):
                label = f"account-{index}"
                started = time.monotonic()
                try:
                    result = checker.check(account, label)
                except Exception as exc:  # isolation boundary for extensions
                    result = CheckinResult(
                        checker.site,
                        label,
                        ResultStatus.FAILED,
                        sanitize_text(exc),
                        time.monotonic() - started,
                    )
                report.results.append(result)
                LOGGER.info("%s %s %s: %s", checker.site, label, result.status, result.summary)

        if notify and report.results:
            for notifier in self.notifiers:
                try:
                    notifier.send(report)
                    report.notifications.append(
                        NotificationResult(notifier.channel, True, "notification sent")
                    )
                except Exception as exc:  # isolation boundary for channels
                    summary = sanitize_text(exc)
                    report.notifications.append(
                        NotificationResult(notifier.channel, False, summary)
                    )
                    LOGGER.error("%s notification failed: %s", notifier.channel, summary)
        return report
