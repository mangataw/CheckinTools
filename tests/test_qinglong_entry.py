from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

import qinglong_checkin


def write_config(tmp_path, monkeypatch, values=""):
    path = tmp_path / "config" / "checkin-tools.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(qinglong_checkin.CONFIG_TEMPLATE + values, encoding="utf-8")
    monkeypatch.setenv("CHECKIN_QINGLONG_CONFIG", str(path))
    return path


def test_cron_metadata_and_source_layout():
    source = Path(qinglong_checkin.__file__).read_text(encoding="utf-8")
    assert "cron: 30 0,8 * * *" in source
    assert "new Env('CheckinTools 每日签到')" in source
    qinglong_checkin._add_source_path()


def test_configured_sites_and_service_dates():
    assert qinglong_checkin._configured_sites({}) == []
    assert qinglong_checkin._configured_sites(
        {"JAVBUS_COOKIES": "a", "FULIBA_USERNAMES": "b", "V2EX_COOKIES": "c"}
    ) == ["javbus", "fuliba", "v2ex"]
    now = datetime(2026, 9, 4, 16, 30, tzinfo=UTC)
    assert qinglong_checkin._state_date("v2ex", now) == "2026-09-04"
    assert qinglong_checkin._state_date("fuliba", now) == "2026-09-05"


def test_main_runs_each_site_with_separate_state(tmp_path, monkeypatch):
    runner = Mock(side_effect=[0, 1])
    monkeypatch.setattr(qinglong_checkin, "_run_cli", runner)
    monkeypatch.setattr(qinglong_checkin, "_add_source_path", Mock())
    path = write_config(tmp_path, monkeypatch)
    path.write_text(
        qinglong_checkin.CONFIG_TEMPLATE.replace("JAVBUS_COOKIES=''", "JAVBUS_COOKIES='cookie-a'")
        .replace("V2EX_USERNAMES=''", "V2EX_USERNAMES='user-b'")
        .replace("V2EX_COOKIES=''", "V2EX_COOKIES='cookie-b'")
        .replace("/ql/data/checkin-tools", tmp_path.as_posix()),
        encoding="utf-8",
    )
    assert qinglong_checkin.main() == 1
    assert runner.call_count == 2
    assert runner.call_args_list[0].args[0][:3] == ["run", "--site", "javbus"]
    assert any("javbus-state.json" in item for item in runner.call_args_list[0].args[0])
    assert any("v2ex-state.json" in item for item in runner.call_args_list[1].args[0])
    assert runner.call_args_list[0].args[1]["JAVBUS_COOKIES"] == "cookie-a"


def test_main_validation_and_lock(tmp_path, monkeypatch):
    path = write_config(tmp_path, monkeypatch)
    assert qinglong_checkin.main() == 2
    path.write_text(
        qinglong_checkin.CONFIG_TEMPLATE.replace(
            "JAVBUS_COOKIES=''", "JAVBUS_COOKIES='cookie'"
        ).replace("/ql/data/checkin-tools", "relative"),
        encoding="utf-8",
    )
    assert qinglong_checkin.main() == 2
    path.write_text(
        qinglong_checkin.CONFIG_TEMPLATE.replace(
            "JAVBUS_COOKIES=''", "JAVBUS_COOKIES='cookie'"
        ).replace("/ql/data/checkin-tools", tmp_path.as_posix()),
        encoding="utf-8",
    )
    monkeypatch.setattr(qinglong_checkin, "_add_source_path", Mock())
    monkeypatch.setattr(qinglong_checkin, "_single_instance", Mock(side_effect=BlockingIOError))
    assert qinglong_checkin.main() == 3


def test_source_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(qinglong_checkin, "__file__", str(tmp_path / "script.py"))
    with pytest.raises(RuntimeError, match="src"):
        qinglong_checkin._add_source_path()


def test_cli_does_not_load_dotenv(monkeypatch):
    import checkin_tools.cli

    runner = Mock(return_value=0)
    monkeypatch.setattr(checkin_tools.cli, "main", runner)
    settings = {"JAVBUS_COOKIES": "from-file"}
    assert qinglong_checkin._run_cli(["run", "--site", "javbus"], settings) == 0
    runner.assert_called_once_with(
        ["run", "--site", "javbus"], environ=settings, load_local_dotenv=False
    )


def test_first_run_creates_complete_template(tmp_path, monkeypatch):
    path = tmp_path / "config" / "checkin-tools.env"
    monkeypatch.setenv("CHECKIN_QINGLONG_CONFIG", str(path))
    assert qinglong_checkin.main() == 2
    text = path.read_text(encoding="utf-8")
    assert set(qinglong_checkin.CONFIG_KEYS) <= {
        line.split("=", 1)[0]
        for line in text.splitlines()
        if "=" in line and not line.startswith("#")
    }
    assert "JavBus" in text and "福利吧" in text and "V2EX" in text
    assert qinglong_checkin._load_settings({"CHECKIN_QINGLONG_CONFIG": str(path)})


def test_file_is_primary_and_multi_account_syntax(tmp_path, monkeypatch):
    from checkin_tools.config import load_config

    path = write_config(tmp_path, monkeypatch)
    path.write_text(
        qinglong_checkin.CONFIG_TEMPLATE.replace(
            "FULIBA_USERNAMES=''", r"FULIBA_USERNAMES='user1\nuser2'"
        ).replace(
            "FULIBA_COOKIES=''", r'''FULIBA_COOKIES='a="1"\nb="2"' '''.rstrip()
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("JAVBUS_COOKIES", "panel-value-must-not-leak")
    _, settings = qinglong_checkin._load_settings({"CHECKIN_QINGLONG_CONFIG": str(path)})
    config = load_config(settings, load_local_dotenv=False)
    assert not config.javbus_cookies
    assert [account.username for account in config.fuliba_accounts] == ["user1", "user2"]
    assert [account.cookie for account in config.fuliba_accounts] == ['a="1"', 'b="2"']


def test_config_file_rejects_unknown_and_bad_path(tmp_path):
    path = tmp_path / "checkin-tools.env"
    path.write_text("UNKNOWN_SECRET='value'\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="UNKNOWN_SECRET"):
        qinglong_checkin._load_settings({"CHECKIN_QINGLONG_CONFIG": str(path)})
    with pytest.raises(RuntimeError, match="绝对路径"):
        qinglong_checkin._load_settings({"CHECKIN_QINGLONG_CONFIG": "relative.env"})
