import base64
import hashlib
import hmac
from urllib.parse import quote_plus

import pytest
import requests

from checkin_tools.config import DingTalkConfig, FeishuConfig, load_config
from checkin_tools.models import CheckinResult, ResultStatus, RunReport
from checkin_tools.notifiers import build_notifiers
from checkin_tools.notifiers.common import format_summary
from checkin_tools.notifiers.dingtalk import (
    DingTalkNotifier,
    NotificationError,
    dingtalk_signature,
)
from checkin_tools.notifiers.feishu import FeishuNotifier, feishu_signature


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def new_session(self):
        return object()

    def post(self, session, path, **kwargs):
        self.calls.append((path, kwargs))
        if isinstance(self.payload, Exception):
            raise self.payload
        return FakeResponse(self.payload)


def report(status=ResultStatus.SUCCESS):
    return RunReport([CheckinResult("site", "account-1", status, "safe summary", 0.1)])


def test_dingtalk_signature_matches_documented_algorithm():
    timestamp, secret = 1700000000123, "example-secret"
    expected = quote_plus(
        base64.b64encode(
            hmac.new(
                secret.encode(), f"{timestamp}\n{secret}".encode(), hashlib.sha256
            ).digest()
        ).decode()
    )
    assert dingtalk_signature(timestamp, secret) == expected


def test_feishu_signature_matches_documented_algorithm():
    timestamp, secret = 1700000000, "example-secret"
    expected = base64.b64encode(
        hmac.new(f"{timestamp}\n{secret}".encode(), digestmod=hashlib.sha256).digest()
    ).decode()
    assert feishu_signature(timestamp, secret) == expected


def test_dingtalk_sends_one_text_payload(monkeypatch):
    monkeypatch.setattr("checkin_tools.notifiers.dingtalk.time.time", lambda: 1700000000.123)
    client = FakeClient({"errcode": 0})
    DingTalkNotifier(DingTalkConfig("example-token", "example-secret"), client=client).send(
        report()
    )
    assert len(client.calls) == 1
    path, kwargs = client.calls[0]
    assert "access_token=example-token" in path
    assert kwargs["json"]["msgtype"] == "text"
    assert "account-1" in kwargs["json"]["text"]["content"]


def test_feishu_sends_one_signed_text_payload(monkeypatch):
    monkeypatch.setattr("checkin_tools.notifiers.feishu.time.time", lambda: 1700000000)
    client = FakeClient({"code": 0})
    notifier = FeishuNotifier(
        FeishuConfig("https://open.feishu.cn/open-apis/bot/v2/hook/example", "secret"),
        client=client,
    )
    notifier.send(report(ResultStatus.ALREADY_DONE))
    path, kwargs = client.calls[0]
    assert path == "/open-apis/bot/v2/hook/example"
    assert kwargs["json"]["timestamp"] == "1700000000"
    assert kwargs["json"]["msg_type"] == "text"


@pytest.mark.parametrize(
    ("notifier", "message"),
    [
        (
            DingTalkNotifier(
                DingTalkConfig("example-token", "example-secret"),
                client=FakeClient({"errcode": 310000}),
            ),
            "DingTalk rejected",
        ),
        (
            FeishuNotifier(
                FeishuConfig("https://example.com/hook", "example-secret"),
                client=FakeClient({"code": 19021}),
            ),
            "Feishu rejected",
        ),
    ],
)
def test_service_errors_are_sanitized(notifier, message):
    with pytest.raises(NotificationError, match=message) as caught:
        notifier.send(report())
    assert "example-secret" not in str(caught.value)


@pytest.mark.parametrize("error", [requests.Timeout("private"), ValueError("private")])
def test_network_and_invalid_response_are_sanitized(error):
    notifier = DingTalkNotifier(
        DingTalkConfig("example-token", "example-secret"), client=FakeClient(error)
    )
    with pytest.raises(NotificationError) as caught:
        notifier.send(report())
    assert "private" not in str(caught.value)


def test_summary_contains_only_expected_aggregate_fields():
    value = format_summary(report(ResultStatus.FAILED))
    assert "Total: 1" in value
    assert "Failed: 1" in value
    assert "account-1" in value
    assert "safe summary" in value
    assert "notification test" in format_summary(RunReport())


def test_build_notifiers_defaults_to_dingtalk_and_can_enable_all():
    config = load_config(
        {
            "DINGTALK_ACCESS_TOKEN": "example-token",
            "DINGTALK_SECRET": "example-secret",
            "FEISHU_WEBHOOK": "https://example.com/hook",
            "FEISHU_SECRET": "example-secret",
        },
        load_local_dotenv=False,
    )
    assert [notifier.channel for notifier in build_notifiers(config)] == ["dingtalk"]
    assert [notifier.channel for notifier in build_notifiers(config, "all")] == [
        "dingtalk",
        "feishu",
    ]
    assert [notifier.channel for notifier in build_notifiers(config, "feishu")] == ["feishu"]


def test_build_notifiers_auto_uses_feishu_when_dingtalk_is_absent():
    config = load_config(
        {
            "FEISHU_WEBHOOK": "https://example.com/hook",
            "FEISHU_SECRET": "example-secret",
        },
        load_local_dotenv=False,
    )
    assert [notifier.channel for notifier in build_notifiers(config)] == ["feishu"]
