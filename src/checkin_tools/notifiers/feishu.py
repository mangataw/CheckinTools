"""Signed Feishu custom robot notifier."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import urlsplit

import requests

from checkin_tools.config import FeishuConfig
from checkin_tools.http import SafeHttpClient
from checkin_tools.interfaces import Notifier
from checkin_tools.models import RunReport
from checkin_tools.notifiers.common import format_summary
from checkin_tools.notifiers.dingtalk import NotificationError


def feishu_signature(timestamp: int, secret: str) -> str:
    signing_key = f"{timestamp}\n{secret}".encode()
    digest = hmac.new(signing_key, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


class FeishuNotifier(Notifier):
    channel = "feishu"

    def __init__(
        self,
        config: FeishuConfig,
        timeout: float = 20,
        retries: int = 2,
        client: SafeHttpClient | None = None,
    ) -> None:
        self.config = config
        parsed = urlsplit(config.webhook)
        origin = f"https://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")
        self.path = parsed.path
        self.client = client or SafeHttpClient(origin, timeout=timeout, retries=retries)

    def send(self, report: RunReport) -> None:
        timestamp = int(time.time())
        body = {
            "timestamp": str(timestamp),
            "sign": feishu_signature(timestamp, self.config.secret),
            "msg_type": "text",
            "content": {"text": format_summary(report)},
        }
        try:
            response = self.client.post(self.client.new_session(), self.path, json=body)
            payload = response.json()
        except requests.RequestException as exc:
            raise NotificationError("Feishu network request failed") from exc
        except ValueError as exc:
            raise NotificationError("Feishu returned an invalid response") from exc
        code = payload.get("code", payload.get("StatusCode"))
        if code != 0:
            raise NotificationError(f"Feishu rejected the message (code {code})")

