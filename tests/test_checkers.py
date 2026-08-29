from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import requests

from checkin_tools.checkers.fuliba import FulibaChecker
from checkin_tools.checkers.javbus import JavBusChecker
from checkin_tools.config import FulibaAccount, load_config
from checkin_tools.http import SafeHttpClient, UnsafeRedirectError
from checkin_tools.models import ResultStatus

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    value = (FIXTURES / name).read_text(encoding="utf-8")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    return value.replace("2026-08-29", today)


class FakeSession:
    def __init__(self):
        self.headers = {}


class FakeClient:
    def __init__(self, responses, base_url="https://example.com"):
        self.responses = list(responses)
        self.sessions = []
        self.validator = SafeHttpClient(base_url, retries=0)

    def new_session(self):
        session = FakeSession()
        self.sessions.append(session)
        return session

    def get(self, session, path):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(text=item)

    def url(self, path):
        return self.validator.url(path)


def config(**values):
    defaults = {
        "JAVBUS_COOKIES": "cookie-one\ncookie-two",
        "FULIBA_USERNAMES": "example-user",
        "FULIBA_COOKIES": "cookie-three",
        "JAVBUS_BASE_URL": "https://example.com",
        "FULIBA_BASE_URL": "https://example.com",
    }
    defaults.update(values)
    return load_config(defaults, load_local_dotenv=False)


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ("javbus_success.html", ResultStatus.SUCCESS),
        ("javbus_already.html", ResultStatus.ALREADY_DONE),
        ("javbus_invalid.html", ResultStatus.FAILED),
    ],
)
def test_javbus_page_states(page, expected):
    checker = JavBusChecker(config(), FakeClient([fixture(page)]))
    result = checker.check("private-cookie", "account-1")
    assert result.status is expected
    assert result.account == "account-1"
    assert "private-cookie" not in result.summary


def test_javbus_rejects_stale_or_changed_record():
    html = fixture("javbus_success.html").replace(
        datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(), "2000-01-01"
    )
    result = JavBusChecker(config(), FakeClient([html])).check("cookie", "account-1")
    assert result.status is ResultStatus.FAILED
    assert "did not confirm" in result.summary


@pytest.mark.parametrize(
    ("error", "summary"),
    [
        (requests.Timeout("private"), "timed out"),
        (requests.ConnectionError("private"), "network request failed"),
        (UnsafeRedirectError("private"), "redirect blocked"),
    ],
)
def test_javbus_sanitizes_request_failures(error, summary):
    result = JavBusChecker(config(), FakeClient([error])).check("cookie", "account-1")
    assert result.status is ResultStatus.FAILED
    assert summary in result.summary
    assert "private" not in result.summary


def test_javbus_uses_independent_sessions():
    client = FakeClient([fixture("javbus_success.html"), fixture("javbus_success.html")])
    checker = JavBusChecker(config(), client)
    for index, cookie in enumerate(checker.accounts, 1):
        checker.check(cookie, f"account-{index}")
    assert len(client.sessions) == 2
    assert client.sessions[0] is not client.sessions[1]
    assert client.sessions[0].headers["Cookie"] == "cookie-one"


def test_fuliba_success_and_post_request_confirmation():
    client = FakeClient(
        [fixture("fuliba_ready.html"), "ignored", fixture("fuliba_done.html")]
    )
    checker = FulibaChecker(config(), client)
    result = checker.check(FulibaAccount("example-user", "cookie"), "account-1")
    assert result.status is ResultStatus.SUCCESS
    assert not client.responses


def test_fuliba_already_done_does_not_request_link():
    client = FakeClient([fixture("fuliba_done.html")])
    result = FulibaChecker(config(), client).check(
        FulibaAccount("example-user", "cookie"), "account-1"
    )
    assert result.status is ResultStatus.ALREADY_DONE
    assert not client.responses


def test_fuliba_rejects_invalid_or_mismatched_login():
    for page, username in (("fuliba_invalid.html", "example-user"), ("fuliba_ready.html", "other")):
        result = FulibaChecker(config(), FakeClient([fixture(page)])).check(
            FulibaAccount(username, "cookie"), "account-1"
        )
        assert result.status is ResultStatus.FAILED
        assert username not in result.summary


def test_fuliba_detects_structure_change_and_unconfirmed_result():
    missing_link = fixture("fuliba_ready.html").replace("function fx_checkin", "function changed")
    result = FulibaChecker(config(), FakeClient([missing_link])).check(
        FulibaAccount("example-user", "cookie"), "account-1"
    )
    assert result.status is ResultStatus.FAILED
    assert "structure changed" in result.summary

    client = FakeClient([fixture("fuliba_ready.html"), "ignored", fixture("fuliba_ready.html")])
    result = FulibaChecker(config(), client).check(
        FulibaAccount("example-user", "cookie"), "account-1"
    )
    assert result.status is ResultStatus.FAILED
    assert "did not confirm" in result.summary


def test_fuliba_blocks_external_checkin_link():
    html = fixture("fuliba_ready.html").replace(
        "plugin.php?id=dsu_paulsign:sign&operation=qiandao", "https://evil.example/plugin.php?id=x"
    )
    result = FulibaChecker(config(), FakeClient([html])).check(
        FulibaAccount("example-user", "cookie"), "account-1"
    )
    assert result.status is ResultStatus.FAILED
    assert "blocked" in result.summary


@pytest.mark.parametrize(
    ("error", "summary"),
    [
        (requests.Timeout("private"), "timed out"),
        (requests.ConnectionError("private"), "network request failed"),
    ],
)
def test_fuliba_sanitizes_network_errors(error, summary):
    result = FulibaChecker(config(), FakeClient([error])).check(
        FulibaAccount("example-user", "cookie"), "account-1"
    )
    assert result.status is ResultStatus.FAILED
    assert summary in result.summary
    assert "private" not in result.summary

