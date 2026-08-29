from checkin_tools import cli


def test_invalid_config_returns_2(monkeypatch):
    monkeypatch.setenv("FULIBA_USERNAMES", "one")
    monkeypatch.delenv("FULIBA_COOKIES", raising=False)
    assert cli.main(["validate-config"]) == 2


def test_valid_but_empty_config_returns_2(monkeypatch):
    for name in (
        "JAVBUS_COOKIES",
        "FULIBA_USERNAMES",
        "FULIBA_COOKIES",
        "DINGTALK_ACCESS_TOKEN",
        "DINGTALK_SECRET",
        "FEISHU_WEBHOOK",
        "FEISHU_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli, "_components", lambda config: ([], []))
    assert cli.main(["validate-config"]) == 2


def test_parser_supports_documented_commands():
    parser = cli.build_parser()
    assert parser.parse_args(["run", "--site", "javbus", "--no-notify"]).site == "javbus"
    assert parser.parse_args(["notify-test", "--channel", "feishu"]).channel == "feishu"

