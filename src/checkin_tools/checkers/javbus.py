"""JavBus forum daily-login checker."""

from __future__ import annotations

import re
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
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class JavBusChecker(Checker):
    site = "javbus"
    display_name = "JavBus"

    def __init__(self, config: AppConfig, client: SafeHttpClient | None = None) -> None:
        self._accounts = config.javbus_cookies
        self.client = client or SafeHttpClient(
            config.javbus_base_url, config.timeout_seconds, config.retries
        )
        self._referer = f"{config.javbus_base_url}/forum/home.php?mod=spacecp"
        self._secrets = config.secrets()

    @property
    def accounts(self):
        return self._accounts

    def check(self, account: str, account_label: str) -> CheckinResult:
        started = time.monotonic()
        retryable = False
        try:
            session = self.client.new_session()
            session.headers.update(
                {**_BROWSER_HEADERS, "Referer": self._referer, "Cookie": account}
            )
            response = self.client.get(session, _CREDIT_LOG_PATH)
            return self._parse(response.text, account_label, started)
        except requests.Timeout:
            summary = "request timed out"
            retryable = True
        except UnsafeRedirectError:
            summary = "unsafe cross-host or non-HTTPS redirect blocked"
        except requests.RequestException:
            summary = "network request failed"
            retryable = True
        except Exception as exc:
            summary = f"unexpected checker error: {sanitize_text(exc, self._secrets)}"
            retryable = False
        return self._result(
            account_label, ResultStatus.FAILED, summary, started, retryable=retryable
        )

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
        timestamp = re.search(
            rf"{re.escape(today)}(?:\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?)?", last_checkin
        )
        confirmed_at = timestamp.group(0) if timestamp else today
        status = (
            ResultStatus.ALREADY_DONE
            if any(marker in html for marker in _ALREADY_MARKERS)
            else ResultStatus.SUCCESS
        )
        summary = (
            f"already checked in today (last check-in: {confirmed_at})"
            if status is ResultStatus.ALREADY_DONE
            else f"checked in (last check-in: {confirmed_at})"
        )
        return self._result(account_label, status, summary, started)

    def _result(
        self,
        account_label: str,
        status: ResultStatus,
        summary: str,
        started: float,
        *,
        retryable: bool = False,
    ) -> CheckinResult:
        return CheckinResult(
            self.site,
            account_label,
            status,
            summary,
            max(0.0, time.monotonic() - started),
            retryable,
        )
