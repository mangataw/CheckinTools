import re
import sys
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from qinglong.DefaultTasks import checkin_base, checkin_setup

TASK_DIR = Path("qinglong/DefaultTasks")
TEMPLATE = Path("qinglong/checkin-tools.env")


def template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def write_config(tmp_path, monkeypatch):
    path = tmp_path / "config" / "checkin-tools.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template_text(), encoding="utf-8")
    monkeypatch.setenv("CHECKIN_QINGLONG_CONFIG", str(path))
    return path


def test_three_task_metadata_and_shared_base_is_not_a_task():
    expected = {
        "checkin_task_javbus.py": "CheckinTools - JavBus 签到",
        "checkin_task_fuliba.py": "CheckinTools - 福利吧签到",
        "checkin_task_v2ex.py": "CheckinTools - V2EX 签到",
    }
    for filename, name in expected.items():
        source = (TASK_DIR / filename).read_text(encoding="utf-8")
        assert "cron: 30 0,8 * * *" in source
        assert f"new Env('{name}')" in source
    base_source = Path(checkin_base.__file__).read_text(encoding="utf-8")
    assert "new Env(" not in base_source
    assert "cron:" not in base_source


def test_single_subscription_prefix_selects_all_qinglong_files():
    filenames = sorted(path.name for path in TASK_DIR.glob("checkin_task_*.py"))
    assert filenames == [
        "checkin_task_fuliba.py",
        "checkin_task_javbus.py",
        "checkin_task_v2ex.py",
    ]
    guide = Path("docs/qinglong.md").read_text(encoding="utf-8")
    assert '"checkin_task_(javbus|fuliba|v2ex)[.]py"' in guide
    assert "checkin_setup.py" in guide


def test_subscription_regex_selects_only_three_task_entries():
    pattern = re.compile(r"checkin_task_(javbus|fuliba|v2ex)[.]py")
    selected = sorted(
        path.name for path in TASK_DIR.glob("*.py") if pattern.search(path.name)
    )
    assert selected == [
        "checkin_task_fuliba.py",
        "checkin_task_javbus.py",
        "checkin_task_v2ex.py",
    ]


def test_setup_is_not_a_task_and_copies_config_only_once(tmp_path):
    source = Path(checkin_setup.__file__).read_text(encoding="utf-8")
    assert "new Env(" not in source
    assert "cron:" not in source
    template = tmp_path / "template.env"
    destination = tmp_path / "config" / "checkin-tools.env"
    template.write_text("VALUE='first'\n", encoding="utf-8")
    assert checkin_setup.ensure_config(template, destination)
    template.write_text("VALUE='second'\n", encoding="utf-8")
    assert not checkin_setup.ensure_config(template, destination)
    assert destination.read_text(encoding="utf-8") == "VALUE='first'\n"


def test_setup_installs_repository_as_editable_package(tmp_path, monkeypatch):
    runner = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(checkin_setup.subprocess, "run", runner)
    assert checkin_setup.install_project(tmp_path) == 0
    command = runner.call_args.args[0]
    assert command[:4] == [sys.executable, "-m", "pip", "install"]
    assert command[-2:] == ["-e", str(tmp_path)]
    runner.assert_called_once_with(command, check=False)


def test_setup_creates_config_before_dependency_failure(monkeypatch):
    events = []
    monkeypatch.setattr(checkin_setup, "ensure_config", lambda: events.append("config"))
    monkeypatch.setattr(
        checkin_setup,
        "install_project",
        lambda: events.append("dependencies") or 1,
    )
    assert checkin_setup.main() == 1
    assert events == ["config", "dependencies"]


def test_template_keys_match_runtime_allowlist():
    from dotenv import dotenv_values

    assert set(dotenv_values(TEMPLATE)) == checkin_base.CONFIG_KEYS


def test_source_layout():
    checkin_base._add_source_path()


def test_site_configuration_and_service_dates():
    assert not checkin_base._site_is_configured("javbus", {})
    assert checkin_base._site_is_configured("javbus", {"JAVBUS_COOKIES": "a"})
    assert checkin_base._site_is_configured("fuliba", {"FULIBA_USERNAMES": "b"})
    assert checkin_base._site_is_configured("v2ex", {"V2EX_COOKIES": "c"})
    now = datetime(2026, 9, 4, 16, 30, tzinfo=UTC)
    assert checkin_base._state_date("v2ex", now) == "2026-09-04"
    assert checkin_base._state_date("fuliba", now) == "2026-09-05"


def test_run_site_uses_its_own_state_and_lock(tmp_path, monkeypatch):
    runner = Mock(return_value=0)
    lock = Mock(side_effect=lambda *_: nullcontext())
    monkeypatch.setattr(checkin_base, "_run_cli", runner)
    monkeypatch.setattr(checkin_base, "_add_source_path", Mock())
    monkeypatch.setattr(checkin_base, "_single_instance", lock)
    path = write_config(tmp_path, monkeypatch)
    path.write_text(
        template_text()
        .replace("V2EX_USERNAMES=''", "V2EX_USERNAMES='user-b'")
        .replace("V2EX_COOKIES=''", "V2EX_COOKIES='cookie-b'")
        .replace("/ql/data/checkin-tools", tmp_path.as_posix()),
        encoding="utf-8",
    )
    assert checkin_base.run_site("v2ex") == 0
    args, settings = runner.call_args.args
    assert args[:3] == ["run", "--site", "v2ex"]
    assert any("v2ex-state.json" in item for item in args)
    assert settings["V2EX_COOKIES"] == "cookie-b"
    lock.assert_called_once_with(tmp_path, "v2ex")


def test_run_site_requires_its_own_account(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch)
    assert checkin_base.run_site("javbus") == 2
    with pytest.raises(ValueError, match="unknown site"):
        checkin_base.run_site("unknown")


def test_run_site_validation_and_lock(tmp_path, monkeypatch):
    path = write_config(tmp_path, monkeypatch)
    path.write_text(
        template_text()
        .replace("JAVBUS_COOKIES=''", "JAVBUS_COOKIES='cookie'")
        .replace("/ql/data/checkin-tools", "relative"),
        encoding="utf-8",
    )
    assert checkin_base.run_site("javbus") == 2
    path.write_text(
        template_text()
        .replace("JAVBUS_COOKIES=''", "JAVBUS_COOKIES='cookie'")
        .replace("/ql/data/checkin-tools", tmp_path.as_posix()),
        encoding="utf-8",
    )
    monkeypatch.setattr(checkin_base, "_add_source_path", Mock())
    monkeypatch.setattr(checkin_base, "_single_instance", Mock(side_effect=BlockingIOError))
    assert checkin_base.run_site("javbus") == 3


def test_source_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(checkin_base, "__file__", str(tmp_path / "runtime.py"))
    with pytest.raises(RuntimeError, match="src/checkin_tools"):
        checkin_base._add_source_path()


def test_cli_does_not_load_dotenv(monkeypatch):
    import checkin_tools.cli

    runner = Mock(return_value=0)
    monkeypatch.setattr(checkin_tools.cli, "main", runner)
    settings = {"JAVBUS_COOKIES": "from-file"}
    assert checkin_base._run_cli(["run", "--site", "javbus"], settings) == 0
    runner.assert_called_once_with(
        ["run", "--site", "javbus"], environ=settings, load_local_dotenv=False
    )


def test_missing_config_is_not_created_by_task(tmp_path, monkeypatch):
    path = tmp_path / "config" / "checkin-tools.env"
    monkeypatch.setenv("CHECKIN_QINGLONG_CONFIG", str(path))
    assert checkin_base.run_site("javbus") == 2
    assert not path.exists()


def test_file_is_primary_and_multi_account_syntax(tmp_path, monkeypatch):
    from checkin_tools.config import load_config

    path = write_config(tmp_path, monkeypatch)
    path.write_text(
        template_text()
        .replace("FULIBA_USERNAMES=''", r"FULIBA_USERNAMES='user1\nuser2'")
        .replace("FULIBA_COOKIES=''", r'''FULIBA_COOKIES='a="1"\nb="2"' '''.rstrip()),
        encoding="utf-8",
    )
    monkeypatch.setenv("JAVBUS_COOKIES", "panel-value-must-not-leak")
    _, settings = checkin_base._load_settings(
        {"CHECKIN_QINGLONG_CONFIG": str(path)}
    )
    config = load_config(settings, load_local_dotenv=False)
    assert not config.javbus_cookies
    assert [account.username for account in config.fuliba_accounts] == ["user1", "user2"]
    assert [account.cookie for account in config.fuliba_accounts] == ['a="1"', 'b="2"']


def test_config_file_rejects_unknown_and_bad_path(tmp_path):
    path = tmp_path / "checkin-tools.env"
    path.write_text("UNKNOWN_SECRET='value'\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="UNKNOWN_SECRET"):
        checkin_base._load_settings({"CHECKIN_QINGLONG_CONFIG": str(path)})
    with pytest.raises(RuntimeError, match="绝对路径"):
        checkin_base._load_settings({"CHECKIN_QINGLONG_CONFIG": "relative.env"})
