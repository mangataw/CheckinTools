import sys
from types import ModuleType

import pytest

from checkin_tools import checkers, config
from checkin_tools.catalog import SiteDefinition
from checkin_tools.contracts import Checker, CheckinResult, ResultStatus
from tools import sync_sites


class ExampleChecker(Checker):
    def __init__(self, app_config, *, definition):
        self.site = definition.id
        self.display_name = definition.display_name

    @property
    def accounts(self):
        return ()

    def check(self, account, account_label):
        return CheckinResult(self.site, account_label, ResultStatus.SUCCESS, "done", 0)


def example_definition() -> SiteDefinition:
    return SiteDefinition(
        id="example",
        display_name="Example",
        base_url="https://example.com",
        credentials={
            "username": "EXAMPLE_USERNAMES",
            "cookie": "EXAMPLE_COOKIES",
        },
        qinglong_cron="15 1 * * *",
        state_timezone="local",
    )


def test_one_site_declaration_drives_config_and_convention_loader(monkeypatch):
    definition = example_definition()
    site_config = config._load_site_config(
        definition,
        {
            "EXAMPLE_USERNAMES": "alice\nbob",
            "EXAMPLE_COOKIES": "cookie-a\ncookie-b",
        },
        enabled=True,
    )
    assert [account.username for account in site_config.accounts] == ["alice", "bob"]
    assert [account.cookie for account in site_config.accounts] == ["cookie-a", "cookie-b"]

    module_name = "checkin_tools.checkers.example"
    module = ModuleType(module_name)
    module.SiteChecker = ExampleChecker
    monkeypatch.setitem(sys.modules, module_name, module)
    checker = checkers._build_checker(None, definition)
    assert checker.site == "example"


def test_loader_reports_missing_module_entrypoint_and_identity(monkeypatch):
    definition = example_definition()
    with pytest.raises(RuntimeError, match="module is missing"):
        checkers._checker_type(definition)

    module_name = "checkin_tools.checkers.example"
    module = ModuleType(module_name)
    monkeypatch.setitem(sys.modules, module_name, module)
    with pytest.raises(RuntimeError, match="must export SiteChecker"):
        checkers._checker_type(definition)

    class WrongChecker(ExampleChecker):
        def __init__(self, app_config, *, definition):
            self.site = "wrong"
            self.display_name = definition.display_name

    module.SiteChecker = WrongChecker
    with pytest.raises(RuntimeError, match="identity does not match"):
        checkers._build_checker(None, definition)


def test_one_site_declaration_drives_every_static_platform(monkeypatch):
    definition = example_definition()
    monkeypatch.setattr(sync_sites, "SITE_DEFINITIONS", (definition,))

    assert "EXAMPLE_COOKIES=''" in sync_sites.render_qinglong_env()
    assert 'run_site("example")' in sync_sites.render_qinglong_task("example")
    assert "cron: 15 1 * * *" in sync_sites.render_qinglong_task("example")
    assert "          - example" in sync_sites.render_actions_options()
    assert "secrets.EXAMPLE_COOKIES" in sync_sites.render_actions_secrets()
