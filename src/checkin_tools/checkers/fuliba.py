"""Fuliba forum checker with identity and post-request verification."""

from __future__ import annotations

import re
import time

import requests
from bs4 import BeautifulSoup

from checkin_tools.config import AppConfig, FulibaAccount
from checkin_tools.http import SafeHttpClient, UnsafeRedirectError
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.security import sanitize_text

_HOME_PATH = "/forum.php?mobile=no"
_SIGNED_MARKERS = (
    "今日已签到",
    "今天已签到",
    "今日已簽到",
    "签到成功",
    "簽到成功",
)


class FulibaChecker(Checker):
    site = "fuliba"
    display_name = "福利吧"

    def __init__(self, config: AppConfig, client: SafeHttpClient | None = None) -> None:
        self._accounts = config.fuliba_accounts
        self.client = client or SafeHttpClient(
            config.fuliba_base_url, config.timeout_seconds, config.retries
        )
        self._secrets = config.secrets()

    @property
    def accounts(self):
        return self._accounts

    def check(self, account: FulibaAccount, account_label: str) -> CheckinResult:
        started = time.monotonic()
        retryable = False
        try:
            session = self.client.new_session()
            session.headers.update({"Cookie": account.cookie})
            before_html = self.client.get(session, _HOME_PATH).text
            before = self._state(before_html)
            if before[0] != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session is invalid or configured username does not match",
                    started,
                )
            if before[3]:
                return self._result(
                    account_label, ResultStatus.ALREADY_DONE, "already checked in today", started
                )

            checkin_path = self._checkin_path(before_html)
            self.client.get(session, checkin_path)
            after = self._state(self.client.get(session, _HOME_PATH).text)
            if after[0] != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session changed while confirming check-in",
                    started,
                )
            if after[3] or (before[2] and after[2] and before[2] != after[2]):
                return self._result(account_label, ResultStatus.SUCCESS, "checked in", started)
            return self._result(
                account_label,
                ResultStatus.FAILED,
                "account state did not confirm a successful check-in",
                started,
            )
        except ValueError as exc:
            summary = sanitize_text(exc, self._secrets)
        except requests.Timeout:
            summary = "request timed out"
            retryable = True
        except UnsafeRedirectError:
            summary = "unsafe check-in link or redirect blocked"
        except requests.RequestException:
            summary = "network request failed"
            retryable = True
        except Exception as exc:
            summary = f"unexpected checker error: {sanitize_text(exc, self._secrets)}"
            retryable = False
        return self._result(
            account_label, ResultStatus.FAILED, summary, started, retryable=retryable
        )

    @staticmethod
    def _state(html: str) -> tuple[str | None, str, str, bool]:
        soup = BeautifulSoup(html, "html.parser")
        profile = soup.find("a", title="访问我的空间")
        username = profile.get_text(strip=True) if profile else None
        tip_node = soup.select_one("div.tip_c")
        checkin_node = soup.select_one("#fx_checkin_menut")
        credit_node = soup.select_one("#extcreditmenu")
        tip = tip_node.get_text(" ", strip=True) if tip_node else ""
        checkin = checkin_node.get_text(" ", strip=True) if checkin_node else ""
        credit = credit_node.get_text(" ", strip=True) if credit_node else ""
        signed = any(marker in f"{tip} {checkin}" for marker in _SIGNED_MARKERS)
        return username, tip, credit, signed

    def _checkin_path(self, html: str) -> str:
        function = re.search(r"function\s+fx_checkin\s*\([^)]*\)\s*\{(.{0,1000}?)\}", html, re.S)
        if not function:
            raise ValueError("check-in page structure changed: function not found")
        candidates = re.findall(r"[\"']([^\"']+)[\"']", function.group(1))
        candidate = next((item for item in candidates if "plugin.php" in item), None)
        if not candidate:
            raise ValueError("check-in page structure changed: link not found")
        self.client.url(candidate)
        return candidate

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
