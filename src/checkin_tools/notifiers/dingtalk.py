"""Signed DingTalk custom robot notifier."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import quote_plus

import requests

from checkin_tools.config import DingTalkConfig
from checkin_tools.http import SafeHttpClient
from checkin_tools.interfaces import Notifier
from checkin_tools.models import RunReport
from checkin_tools.notifiers.common import format_summary


class NotificationError(RuntimeError):
    pass


def dingtalk_signature(timestamp_ms: int, secret: str) -> str:
    message = f"{timestamp_ms}\n{secret}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return quote_plus(base64.b64encode(digest).decode())


class DingTalkNotifier(Notifier):
    channel = "dingtalk"

    def __init__(
        self,
        config: DingTalkConfig,
        timeout: float = 20,
        retries: int = 2,
        client: SafeHttpClient | None = None,
    ) -> None:
        self.config = config
        self.client = client or SafeHttpClient(
            "https://oapi.dingtalk.com", timeout=timeout, retries=retries
        )

    def send(self, report: RunReport) -> None:
        timestamp = int(time.time() * 1000)
        signature = dingtalk_signature(timestamp, self.config.secret)
        path = (
            "/robot/send?access_token="
            f"{quote_plus(self.config.access_token)}&timestamp={timestamp}&sign={signature}"
        )
        try:
            response = self.client.post(
                self.client.new_session(),
                path,
                json={"msgtype": "text", "text": {"content": format_summary(report)}},
            )
            payload = response.json()
        except requests.RequestException as exc:
            raise NotificationError("DingTalk network request failed") from exc
        except ValueError as exc:
            raise NotificationError("DingTalk returned an invalid response") from exc
        if payload.get("errcode") != 0:
            raise NotificationError(
                f"DingTalk rejected the message (code {payload.get('errcode')})"
            )
