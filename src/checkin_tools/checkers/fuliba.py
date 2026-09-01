"""Fuliba forum checker with identity and post-request verification."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

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
)
_SIGNED_RANK_PATTERN = re.compile(r"(?:您)?今日第\s*\d+\s*(?:个|個)签到")

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _AccountState:
    username: str | None
    tip: str
    credit: str
    signed_today: bool


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
            if before.username != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session is invalid or configured username does not match",
                    started,
                )
            LOGGER.info(
                "%s %s pre-check: signed_today=%s; tip=%s; credit=%s",
                self.site,
                account_label,
                before.signed_today,
                self._log_value(before.tip),
                self._log_value(before.credit),
            )
            if before.signed_today:
                return self._result(
                    account_label,
                    ResultStatus.ALREADY_DONE,
                    self._summary("already checked in today", before),
                    started,
                )

            checkin_path = self._checkin_path(before_html)
            self.client.get(session, checkin_path)
            LOGGER.info("%s %s check-in request completed", self.site, account_label)
            after = self._state(self.client.get(session, _HOME_PATH).text)
            if after.username != account.username:
                return self._result(
                    account_label,
                    ResultStatus.FAILED,
                    "login session changed while confirming check-in",
                    started,
                )
            evidence = self._confirmation_evidence(before, after)
            LOGGER.info(
                "%s %s post-check: confirmed_by=%s; tip=%s; credit=%s",
                self.site,
                account_label,
                ",".join(evidence) if evidence else "none",
                self._log_value(after.tip),
                self._log_value(after.credit),
            )
            if evidence:
                return self._result(
                    account_label,
                    ResultStatus.SUCCESS,
                    self._summary(
                        f"checked in; confirmed by {', '.join(evidence)}", after
                    ),
                    started,
                )
            return self._result(
                account_label,
                ResultStatus.FAILED,
                "check-in request completed but account state did not confirm success "
                "(daily marker absent; tip unchanged; credit unchanged)",
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
    def _state(html: str) -> _AccountState:
        soup = BeautifulSoup(html, "html.parser")
        profile = soup.find("a", title="访问我的空间")
        username = profile.get_text(strip=True) if profile else None
        tip_node = soup.select_one("div.tip_c")
        credit_node = soup.select_one("#extcreditmenu")
        tip = tip_node.get_text(" ", strip=True) if tip_node else ""
        credit = credit_node.get_text(" ", strip=True) if credit_node else ""
        signed = any(marker in tip for marker in _SIGNED_MARKERS) or bool(
            _SIGNED_RANK_PATTERN.search(tip)
        )
        return _AccountState(username, tip, credit, signed)

    @staticmethod
    def _confirmation_evidence(before: _AccountState, after: _AccountState) -> list[str]:
        evidence = []
        if after.signed_today:
            evidence.append("daily status marker")
        if after.tip and after.tip != before.tip:
            evidence.append("check-in tip changed")
        if before.credit and after.credit and before.credit != after.credit:
            evidence.append("credit changed")
        return evidence

    @classmethod
    def _summary(cls, message: str, state: _AccountState) -> str:
        details = []
        if state.tip:
            details.append(f"tip={cls._log_value(state.tip)}")
        if state.credit:
            details.append(f"credit={cls._log_value(state.credit)}")
        return f"{message} ({'; '.join(details)})" if details else message

    @staticmethod
    def _log_value(value: str) -> str:
        compact = " ".join(value.split())
        return compact[:157] + "..." if len(compact) > 160 else compact or "<absent>"

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
