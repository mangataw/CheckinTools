"""Notification summary formatting."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from checkin_tools.models import ResultStatus, RunReport


def format_summary(report: RunReport) -> str:
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %Z")
    if not report.results:
        return f"CheckinTools notification test\nTime: {now}"
    lines = [
        "CheckinTools check-in summary",
        f"Time: {now}",
        (
            f"Total: {len(report.results)} | Success: {report.count(ResultStatus.SUCCESS)} | "
            f"Already: {report.count(ResultStatus.ALREADY_DONE)} | "
            f"Failed: {report.count(ResultStatus.FAILED)}"
        ),
    ]
    lines.extend(
        f"{item.site} {item.account}: {item.status.value} - {item.summary}"
        for item in report.results
    )
    return "\n".join(lines)

