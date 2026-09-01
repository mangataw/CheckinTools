"""V2EX daily mission checker with identity and balance-ledger verification."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup

from checkin_tools.config import AppConfig, V2exAccount
from checkin_tools.http import SafeHttpClient, UnsafeRedirectError
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.security import sanitize_text

_MISSION_PATH = "/mission/daily"
_BALANCE_PATH = "/balance"
_BUTTON_TARGET_PATTERN = re.compile(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]")
_REDEEM_PATTERN = re.compile(
    r'(?:https?://[^/"\'\s<>]+)?/mission/daily/redeem\?once=\d+'
)
_STREAK_PATTERN = re.compile(r"(?:已连续登录|已連續登錄)\s*\d+\s*天")
_LEDGER_REWARD_PATTERN = re.compile(
    r"(?P<date>\d{8}).*?(?:每日登录奖励|每日登錄獎勵)\s*"
    r"(?P<reward>\d+)\s*(?:个|個)?\s*铜币"
)
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _MissionState:
    username: str | None
    action: str
    target: str | None
    streak: str


@dataclass(frozen=True, slots=True)
class _BalanceEntry:
    timestamp: str
    reward: str
    total: str


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
            before = self._mission_state(self.client.get(session, _MISSION_PATH).text)
            if before.username != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session is invalid or configured username does not match",
                    started,
                )
            LOGGER.info(
                "%s %s pre-check: service_date=%s; action=%s; streak=%s",
                self.site,
                account_label,
                self._service_date(),
                before.action,
                before.streak or "<absent>",
            )

            if before.action == "balance":
                entry = self._today_balance_entry(
                    self.client.get(session, _BALANCE_PATH).text
                )
                if not entry:
                    return self._result(
                        account_label,
                        ResultStatus.FAILED,
                        "mission page indicates claimed but balance page has no daily reward "
                        "entry for the current V2EX UTC day",
                        started,
                    )
                return self._result(
                    account_label,
                    ResultStatus.ALREADY_DONE,
                    self._summary("daily login reward already claimed", entry, before.streak),
                    started,
                )

            if before.action != "redeem" or not before.target:
                raise ValueError("daily mission page structure changed: action button is invalid")
            self.client.url(before.target)
            self.client.get(session, before.target)
            LOGGER.info("%s %s redeem request completed", self.site, account_label)

            after = self._mission_state(self.client.get(session, _MISSION_PATH).text)
            if after.username != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session changed while confirming daily reward",
                    started,
                )
            LOGGER.info(
                "%s %s post-check: action=%s; streak=%s",
                self.site,
                account_label,
                after.action,
                after.streak or "<absent>",
            )
            if after.action != "balance":
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "daily mission action did not change to balance after redeem request",
                    started,
                )

            entry = self._today_balance_entry(self.client.get(session, _BALANCE_PATH).text)
            if not entry:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "balance page did not confirm a daily reward entry for the current "
                    "V2EX UTC day",
                    started,
                )
            LOGGER.info(
                "%s %s balance confirmed: timestamp=%s; reward=%s; total=%s",
                self.site,
                account_label,
                entry.timestamp,
                entry.reward,
                entry.total,
            )
            return self._result(
                account_label,
                ResultStatus.SUCCESS,
                self._summary("daily login reward claimed", entry, after.streak),
                started,
            )
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
    def _mission_state(html: str) -> _MissionState:
        soup = BeautifulSoup(html, "html.parser")
        profile = soup.select_one('a.top[href^="/member/"]')
        username = profile.get_text(" ", strip=True) if profile else None
        button = soup.select_one("input.super.normal.button")
        onclick = button.get("onclick", "") if button else ""
        target_match = _BUTTON_TARGET_PATTERN.search(str(onclick))
        target = target_match.group(1) if target_match else None
        if target == _BALANCE_PATH:
            action = "balance"
        elif target and _REDEEM_PATTERN.fullmatch(target):
            action = "redeem"
        else:
            action = "invalid"
        streak_match = _STREAK_PATTERN.search(soup.get_text(" ", strip=True))
        streak = streak_match.group(0) if streak_match else ""
        return _MissionState(username, action, target, streak)

    @staticmethod
    def _today_balance_entry(html: str) -> _BalanceEntry | None:
        service_date = V2exChecker._service_date()
        soup = BeautifulSoup(html, "html.parser")
        for row in soup.select("table.data tr"):
            cells = row.select("td.d")
            if len(cells) < 5:
                continue
            description = cells[4].get_text(" ", strip=True)
            match = _LEDGER_REWARD_PATTERN.search(description)
            if match and match.group("date") == service_date:
                return _BalanceEntry(
                    cells[0].get_text(" ", strip=True),
                    match.group("reward"),
                    cells[3].get_text(" ", strip=True),
                )
        return None

    @staticmethod
    def _service_date() -> str:
        """Return the calendar day used by V2EX daily missions (UTC)."""
        return datetime.now(UTC).strftime("%Y%m%d")

    @staticmethod
    def _summary(message: str, entry: _BalanceEntry, streak: str) -> str:
        details = [
            f"reward={entry.reward} coins",
            f"total={entry.total}",
            f"timestamp={entry.timestamp}",
        ]
        if streak:
            details.append(f"streak={streak}")
        return f"{message} ({'; '.join(details)})"

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
