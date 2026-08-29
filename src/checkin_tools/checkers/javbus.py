"""JavBus forum daily-login checker."""

from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from checkin_tools.config import AppConfig
from checkin_tools.http import SafeHttpClient, UnsafeRedirectError
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.security import sanitize_text

_CREDIT_LOG_PATH = "/forum/home.php?mod=spacecp&ac=credit&op=log&suboperation=creditrulelog"
_DAILY_MARKERS = ("每天登录", "每天登錄")
_ALREADY_MARKERS = ("今日已签到", "今天已签到", "今日已簽到")


class JavBusChecker(Checker):
    site = "javbus"
    display_name = "JavBus"

    def __init__(self, config: AppConfig, client: SafeHttpClient | None = None) -> None:
        self._accounts = config.javbus_cookies
        self.client = client or SafeHttpClient(
            config.javbus_base_url, config.timeout_seconds, config.retries
        )
        self._secrets = config.secrets()

    @property
    def accounts(self):
        return self._accounts

    def check(self, account: str, account_label: str) -> CheckinResult:
        started = time.monotonic()
        try:
            session = self.client.new_session()
            session.headers.update({"Cookie": account})
            response = self.client.get(session, _CREDIT_LOG_PATH)
            return self._parse(response.text, account_label, started)
        except requests.Timeout:
            summary = "request timed out"
        except UnsafeRedirectError:
            summary = "unsafe cross-host or non-HTTPS redirect blocked"
        except requests.RequestException:
            summary = "network request failed"
        except Exception as exc:
            summary = f"unexpected checker error: {sanitize_text(exc, self._secrets)}"
        return self._result(account_label, ResultStatus.FAILED, summary, started)

    def _parse(self, html: str, account_label: str, started: float) -> CheckinResult:
        if not any(marker in html for marker in _DAILY_MARKERS):
            return self._result(
                account_label,
                ResultStatus.FAILED,
                "login session is invalid or daily-login rule is unavailable",
                started,
            )

        soup = BeautifulSoup(html, "html.parser")
        daily_row = next(
            (
                row
                for row in soup.select("tr")
                if any(marker in row.get_text() for marker in _DAILY_MARKERS)
            ),
            None,
        )
        cells = daily_row.select("td") if daily_row else []
        last_checkin = cells[5].get_text(" ", strip=True) if len(cells) >= 6 else ""
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        if not last_checkin or today not in last_checkin:
            return self._result(
                account_label,
                ResultStatus.FAILED,
                "daily-login record did not confirm today's check-in",
                started,
            )
        status = (
            ResultStatus.ALREADY_DONE
            if any(marker in html for marker in _ALREADY_MARKERS)
            else ResultStatus.SUCCESS
        )
        summary = (
            "already checked in today" if status is ResultStatus.ALREADY_DONE else "checked in"
        )
        return self._result(account_label, status, summary, started)

    def _result(
        self, account_label: str, status: ResultStatus, summary: str, started: float
    ) -> CheckinResult:
        return CheckinResult(
            self.site, account_label, status, summary, max(0.0, time.monotonic() - started)
        )
