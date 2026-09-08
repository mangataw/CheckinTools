import sys
from types import ModuleType

from checkin_tools import checkers, config
from checkin_tools.interfaces import Checker
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.site_catalog import CredentialField, SiteDefinition
from tools import sync_sites


class ExampleChecker(Checker):
    site = "example"
    display_name = "Example"

    @property
    def accounts(self):
        return ()

    def check(self, account, account_label):
        return CheckinResult(self.site, account_label, ResultStatus.SUCCESS, "done", 0)


def example_definition() -> SiteDefinition:
    return SiteDefinition(
        site="example",
        display_name="Example",
        summary="Example 每日签到",
        documentation="docs/example.md",
        checker_module="test_example_checker",
        checker_class="ExampleChecker",
        qinglong_task_name="CheckinTools - Example 签到",
        credential_fields=(
            CredentialField(
                "username",
                "EXAMPLE_USERNAMES",
                "用户名",
                r"user_one\nuser_two",
                "Example 用户名，每行一个",
            ),
            CredentialField(
                "cookie",
                "EXAMPLE_COOKIES",
                "Cookie",
                r"cookie_one\ncookie_two",
                "Example Cookie，与用户名按行对应",
            ),
        ),
        base_url_key="EXAMPLE_BASE_URL",
        default_base_url="https://example.com",
    )


def test_one_site_declaration_drives_config_loader_and_checker_import(monkeypatch):
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

    module = ModuleType(definition.checker_module)
    module.ExampleChecker = ExampleChecker
    monkeypatch.setitem(sys.modules, definition.checker_module, module)
    assert checkers._checker_type(definition) is ExampleChecker


def test_one_site_declaration_drives_every_static_platform(monkeypatch):
    definition = example_definition()
    monkeypatch.setattr(sync_sites, "SITE_DEFINITIONS", (definition,))

    assert "EXAMPLE_USERNAMES='user_one\\nuser_two'" in sync_sites.render_local_env()
    assert "EXAMPLE_COOKIES=''" in sync_sites.render_qinglong_env()
    assert 'run_site("example")' in sync_sites.render_qinglong_task("example")
    assert "          - example" in sync_sites.render_actions_options()
    assert "secrets.EXAMPLE_COOKIES" in sync_sites.render_actions_secrets()
    assert "Example 每日签到" in sync_sites.render_readme_features()
    assert "docs/example.md" in sync_sites.render_readme_docs()
    assert "example-state.json" in sync_sites.render_qinglong_state_files()
