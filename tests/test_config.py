import pytest

from checkin_tools.config import ConfigError, load_config, validate_base_url


def test_load_complete_multiline_config():
    config = load_config(
        {
            "JAVBUS_COOKIES": " one \\n two\n",
            "FULIBA_USERNAMES": "alice\nbob",
            "FULIBA_COOKIES": "cookie-a\ncookie-b",
            "DINGTALK_ACCESS_TOKEN": "token",
            "DINGTALK_SECRET": "secret",
            "FEISHU_WEBHOOK": "https://open.feishu.cn/open-apis/bot/v2/hook/example",
            "FEISHU_SECRET": "secret-2",
            "CHECKIN_TIMEOUT_SECONDS": "3.5",
            "CHECKIN_RETRIES": "4",
        },
        load_local_dotenv=False,
    )
    assert config.javbus_cookies == ("one", "two")
    assert [account.username for account in config.fuliba_accounts] == ["alice", "bob"]
    assert config.timeout_seconds == 3.5
    assert config.retries == 4
    assert config.dingtalk and config.feishu
    assert config.notify_channel == "auto"
    assert config.notify_mode == "summary"
    assert "cookie-a" in config.secrets()


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?query=yes",
        "https://example.com/#fragment",
    ],
)
def test_rejects_unsafe_base_urls(value):
    with pytest.raises(ConfigError):
        validate_base_url(value, "TEST_URL")


def test_normalizes_base_url():
    assert validate_base_url("https://EXAMPLE.com/", "URL") == "https://example.com"


def test_rejects_mismatched_fuliba_accounts():
    with pytest.raises(ConfigError, match="same line count"):
        load_config(
            {"FULIBA_USERNAMES": "one\ntwo", "FULIBA_COOKIES": "cookie"},
            load_local_dotenv=False,
        )


@pytest.mark.parametrize(
    "values",
    [
        {"DINGTALK_ACCESS_TOKEN": "token"},
        {"DINGTALK_SECRET": "secret"},
        {"FEISHU_WEBHOOK": "https://example.com/hook"},
        {"FEISHU_SECRET": "secret"},
    ],
)
def test_rejects_partial_notification_config(values):
    with pytest.raises(ConfigError, match="requires both"):
        load_config(values, load_local_dotenv=False)


@pytest.mark.parametrize(
    "access_token",
    [
        "https://oapi.dingtalk.com/robot/send?access_token=token",
        "access_token=token",
    ],
)
def test_rejects_dingtalk_webhook_instead_of_access_token(access_token):
    with pytest.raises(ConfigError, match="only the value after access_token="):
        load_config(
            {
                "DINGTALK_ACCESS_TOKEN": access_token,
                "DINGTALK_SECRET": "secret",
            },
            load_local_dotenv=False,
        )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("CHECKIN_TIMEOUT_SECONDS", "zero"),
        ("CHECKIN_TIMEOUT_SECONDS", "0"),
        ("CHECKIN_RETRIES", "-1"),
        ("CHECKIN_RETRIES", "11"),
    ],
)
def test_rejects_invalid_http_settings(key, value):
    with pytest.raises(ConfigError):
        load_config({key: value}, load_local_dotenv=False)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("CHECKIN_NOTIFY_CHANNEL", "unknown", "must be auto"),
        ("CHECKIN_NOTIFY_MODE", "batch", "must be summary"),
        ("CHECKIN_NOTIFY_CHANNEL", "dingtalk", "not configured"),
        ("CHECKIN_NOTIFY_CHANNEL", "feishu", "not configured"),
    ],
)
def test_rejects_invalid_notification_routing(key, value, message):
    with pytest.raises(ConfigError, match=message):
        load_config({key: value}, load_local_dotenv=False)


def test_loads_explicit_notification_routing():
    config = load_config(
        {
            "DINGTALK_ACCESS_TOKEN": "token",
            "DINGTALK_SECRET": "secret",
            "CHECKIN_NOTIFY_CHANNEL": "dingtalk",
            "CHECKIN_NOTIFY_MODE": "individual",
        },
        load_local_dotenv=False,
    )
    assert config.notify_channel == "dingtalk"
    assert config.notify_mode == "individual"
