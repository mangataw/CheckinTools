import os

import pytest

from checkin_tools import cli
from checkin_tools.config import load_config
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus


@pytest.fixture(autouse=True)
def isolate_cli_tests_from_local_dotenv(monkeypatch):
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: load_config(os.environ, load_local_dotenv=False),
    )


class CliChecker(Checker):
    site = "javbus"
    display_name = "Test"

    def __init__(self):
        self.calls = 0

    @property
    def accounts(self):
        return ("private",)

    def check(self, account, account_label):
        self.calls += 1
        return CheckinResult(self.site, account_label, ResultStatus.SUCCESS, "done", 0.1)


def test_invalid_config_returns_2(monkeypatch):
    monkeypatch.setenv("FULIBA_USERNAMES", "one")
    monkeypatch.delenv("FULIBA_COOKIES", raising=False)
    assert cli.main(["validate-config"]) == 2


def test_valid_but_empty_config_returns_2(monkeypatch):
    for name in (
        "JAVBUS_COOKIES",
        "FULIBA_USERNAMES",
        "FULIBA_COOKIES",
        "V2EX_USERNAMES",
        "V2EX_COOKIES",
        "DINGTALK_ACCESS_TOKEN",
        "DINGTALK_SECRET",
        "FEISHU_WEBHOOK",
        "FEISHU_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli, "_components", lambda config, selection=None: ([], []))
    assert cli.main(["validate-config"]) == 2


def test_parser_supports_documented_commands():
    parser = cli.build_parser()
    assert parser.parse_args(["run", "--site", "javbus", "--no-notify"]).site == "javbus"
    assert parser.parse_args(["run", "--site", "v2ex", "--no-notify"]).site == "v2ex"
    assert parser.parse_args(["notify-test", "--channel", "feishu"]).channel == "feishu"


def test_cli_daily_state_skips_terminal_account_on_second_run(monkeypatch, tmp_path):
    checker = CliChecker()
    monkeypatch.setattr(
        cli, "_components", lambda config, selection=None: ([checker], [])
    )
    state_path = tmp_path / "state.json"
    args = [
        "run",
        "--site",
        "javbus",
        "--no-notify",
        "--state-file",
        str(state_path),
        "--state-date",
        "2026-08-29",
    ]
    assert cli.main(args) == 0
    assert cli.main(args) == 0
    assert checker.calls == 1


def test_cli_rejects_corrupt_daily_state(monkeypatch, tmp_path):
    checker = CliChecker()
    monkeypatch.setattr(
        cli, "_components", lambda config, selection=None: ([checker], [])
    )
    state_path = tmp_path / "state.json"
    state_path.write_text("invalid")
    assert (
        cli.main(
            [
                "run",
                "--no-notify",
                "--state-file",
                str(state_path),
                "--state-date",
                "2026-08-29",
            ]
        )
        == 2
    )
