"""V2EX daily mission checker with identity and post-request verification."""

from __future__ import annotations

import re
import time

import requests
from bs4 import BeautifulSoup

from checkin_tools.config import AppConfig, V2exAccount
from checkin_tools.http import SafeHttpClient, UnsafeRedirectError
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.security import sanitize_text

_MISSION_PATH = "/mission/daily"
_CLAIMED_MARKERS = ("每日登录奖励已领取", "每日登錄獎勵已領取")
_SUCCESS_MARKERS = ("已成功领取每日登录奖励", "已成功領取每日登錄獎勵")
_LOGIN_MARKERS = ("需要先登录", "需要先登錄", "/signin")
_REDEEM_PATTERN = re.compile(
    r'(?:https?://[^/"\'\s<>]+)?/mission/daily/redeem\?once=\d+'
)
_REWARD_PATTERN = re.compile(r"(?:奖励|獎勵)\s*(\d+)\s*(?:个|個)?\s*铜币")
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class V2exChecker(Checker):
    site = "v2ex"
    display_name = "V2EX"

    def __init__(self, config: AppConfig, client: SafeHttpClient | None = None) -> None:
        self._accounts = config.v2ex_accounts
        self.client = client or SafeHttpClient(
            config.v2ex_base_url, config.timeout_seconds, config.retries
        )
        self._referer = f"{config.v2ex_base_url}{_MISSION_PATH}"
        self._secrets = config.secrets()

    @property
    def accounts(self):
        return self._accounts

    def check(self, account: V2exAccount, account_label: str) -> CheckinResult:
        started = time.monotonic()
        retryable = False
        try:
            session = self.client.new_session()
            session.headers.update(
                {**_BROWSER_HEADERS, "Referer": self._referer, "Cookie": account.cookie}
            )
            before_html = self.client.get(session, _MISSION_PATH).text
            username, claimed = self._state(before_html)
            if username != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session is invalid or configured username does not match",
                    started,
                )
            if claimed:
                return self._result(
                    account_label,
                    ResultStatus.ALREADY_DONE,
                    "daily login reward already claimed",
                    started,
                )

            redeem_path = self._redeem_path(before_html)
            redeem_html = self.client.get(session, redeem_path).text
            after_html = self.client.get(session, _MISSION_PATH).text
            after_username, after_claimed = self._state(after_html)
            if after_username != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session changed while confirming daily reward",
                    started,
                )
            if not after_claimed:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "daily mission page did not confirm a claimed reward",
                    started,
                )

            reward = self._reward(redeem_html)
            summary = (
                f"daily login reward claimed ({reward} coins)"
                if reward
                else "daily login reward claimed"
            )
            return self._result(account_label, ResultStatus.SUCCESS, summary, started)
        except ValueError as exc:
            summary = sanitize_text(exc, self._secrets)
        except requests.Timeout:
            summary = "request timed out"
            retryable = True
        except UnsafeRedirectError:
            summary = "unsafe daily mission link or redirect blocked"
        except requests.RequestException:
            summary = "network request failed"
            retryable = True
        except Exception as exc:
            summary = f"unexpected checker error: {sanitize_text(exc, self._secrets)}"
        return self._result(
            account_label, ResultStatus.FAILED, summary, started, retryable=retryable
        )

    @staticmethod
    def _state(html: str) -> tuple[str | None, bool]:
        soup = BeautifulSoup(html, "html.parser")
        profile = soup.select_one('a.top[href^="/member/"]')
        username = profile.get_text(" ", strip=True) if profile else None
        claimed = any(marker in html for marker in _CLAIMED_MARKERS)
        return username, claimed

    def _redeem_path(self, html: str) -> str:
        if any(marker in html for marker in _LOGIN_MARKERS):
            raise ValueError("login session is invalid")
        match = _REDEEM_PATTERN.search(html)
        if not match:
            raise ValueError("daily mission page structure changed: redeem link not found")
        path = match.group(0)
        self.client.url(path)
        return path

    @staticmethod
    def _reward(html: str) -> str | None:
        if not any(marker in html for marker in _SUCCESS_MARKERS):
            return None
        match = _REWARD_PATTERN.search(BeautifulSoup(html, "html.parser").get_text(" "))
        return match.group(1) if match else None

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
