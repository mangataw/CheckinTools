"""Canonical metadata for built-in check-in sites."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CredentialField:
    """One line-oriented account field supplied through an environment variable."""

    name: str
    env_key: str
    display_name: str
    example: str


@dataclass(frozen=True, slots=True)
class SiteDefinition:
    site: str
    display_name: str
    checker_module: str
    checker_class: str
    qinglong_task_name: str
    credential_fields: tuple[CredentialField, ...]
    base_url_key: str
    default_base_url: str
    qinglong_cron: str = "30 0,8 * * *"

    @property
    def credential_keys(self) -> tuple[str, ...]:
        return tuple(field.env_key for field in self.credential_fields)

    @property
    def config_keys(self) -> tuple[str, ...]:
        return (*self.credential_keys, self.base_url_key)


SITE_DEFINITIONS = (
    SiteDefinition(
        site="javbus",
        display_name="JavBus",
        checker_module="checkin_tools.checkers.javbus",
        checker_class="JavBusChecker",
        qinglong_task_name="CheckinTools - JavBus 签到",
        credential_fields=(
            CredentialField(
                "cookie",
                "JAVBUS_COOKIES",
                "Cookie",
                r"example_cookie_one\nexample_cookie_two",
            ),
        ),
        base_url_key="JAVBUS_BASE_URL",
        default_base_url="https://www.javbus.com",
    ),
    SiteDefinition(
        site="fuliba",
        display_name="福利吧",
        checker_module="checkin_tools.checkers.fuliba",
        checker_class="FulibaChecker",
        qinglong_task_name="CheckinTools - 福利吧签到",
        credential_fields=(
            CredentialField(
                "username",
                "FULIBA_USERNAMES",
                "用户名",
                r"example_user_one\nexample_user_two",
            ),
            CredentialField(
                "cookie",
                "FULIBA_COOKIES",
                "Cookie",
                r"example_cookie_one\nexample_cookie_two",
            ),
        ),
        base_url_key="FULIBA_BASE_URL",
        default_base_url="https://www.wnflb2023.com",
    ),
    SiteDefinition(
        site="v2ex",
        display_name="V2EX",
        checker_module="checkin_tools.checkers.v2ex",
        checker_class="V2exChecker",
        qinglong_task_name="CheckinTools - V2EX 签到",
        credential_fields=(
            CredentialField(
                "username",
                "V2EX_USERNAMES",
                "用户名",
                r"example_user_one\nexample_user_two",
            ),
            CredentialField(
                "cookie",
                "V2EX_COOKIES",
                "Cookie",
                r"example_cookie_one\nexample_cookie_two",
            ),
        ),
        base_url_key="V2EX_BASE_URL",
        default_base_url="https://www.v2ex.com",
    ),
)

SITE_IDS = tuple(definition.site for definition in SITE_DEFINITIONS)
SITE_CONFIG_KEYS = frozenset(
    key for definition in SITE_DEFINITIONS for key in definition.config_keys
)
_SITES_BY_ID = {definition.site: definition for definition in SITE_DEFINITIONS}


def site_definition(site: str) -> SiteDefinition:
    try:
        return _SITES_BY_ID[site]
    except KeyError as exc:
        raise ValueError(f"unknown site: {site}") from exc
