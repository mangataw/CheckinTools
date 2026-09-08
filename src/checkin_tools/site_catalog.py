"""Canonical metadata for built-in check-in sites."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CredentialField:
    """One line-oriented account field supplied through an environment variable."""

    name: str
    env_key: str
    display_name: str
    example: str
    description: str


@dataclass(frozen=True, slots=True)
class SiteDefinition:
    site: str
    display_name: str
    summary: str
    documentation: str
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
        summary="JavBus 论坛每日登录积分",
        documentation="docs/javbus.md",
        checker_module="checkin_tools.checkers.javbus",
        checker_class="JavBusChecker",
        qinglong_task_name="CheckinTools - JavBus 签到",
        credential_fields=(
            CredentialField(
                "cookie",
                "JAVBUS_COOKIES",
                "Cookie",
                r"example_cookie_one\nexample_cookie_two",
                "JavBus，每行一个账号 Cookie",
            ),
        ),
        base_url_key="JAVBUS_BASE_URL",
        default_base_url="https://www.javbus.com",
    ),
    SiteDefinition(
        site="fuliba",
        display_name="福利吧",
        summary="福利吧签到",
        documentation="docs/fuliba.md",
        checker_module="checkin_tools.checkers.fuliba",
        checker_class="FulibaChecker",
        qinglong_task_name="CheckinTools - 福利吧签到",
        credential_fields=(
            CredentialField(
                "username",
                "FULIBA_USERNAMES",
                "用户名",
                r"example_user_one\nexample_user_two",
                "福利吧用户名，每行一个",
            ),
            CredentialField(
                "cookie",
                "FULIBA_COOKIES",
                "Cookie",
                r"example_cookie_one\nexample_cookie_two",
                "福利吧 Cookie，与用户名按行对应",
            ),
        ),
        base_url_key="FULIBA_BASE_URL",
        default_base_url="https://www.wnflb2023.com",
    ),
    SiteDefinition(
        site="v2ex",
        display_name="V2EX",
        summary="V2EX 每日登录奖励",
        documentation="docs/v2ex.md",
        checker_module="checkin_tools.checkers.v2ex",
        checker_class="V2exChecker",
        qinglong_task_name="CheckinTools - V2EX 签到",
        credential_fields=(
            CredentialField(
                "username",
                "V2EX_USERNAMES",
                "用户名",
                r"example_user_one\nexample_user_two",
                "V2EX 用户名，每行一个",
            ),
            CredentialField(
                "cookie",
                "V2EX_COOKIES",
                "Cookie",
                r"example_cookie_one\nexample_cookie_two",
                "V2EX 完整 Cookie，与用户名按行对应",
            ),
        ),
        base_url_key="V2EX_BASE_URL",
        default_base_url="https://www.v2ex.com",
    ),
)

_SITE_PATTERN = re.compile(r"[a-z0-9_]+")
_ENV_KEY_PATTERN = re.compile(r"[A-Z][A-Z0-9_]+")


def validate_site_definitions(
    definitions: tuple[SiteDefinition, ...] = SITE_DEFINITIONS,
) -> None:
    """Reject catalog declarations that cannot be loaded or generated safely."""
    if not definitions:
        raise ValueError("site catalog must not be empty")

    site_ids: set[str] = set()
    config_keys: set[str] = set()
    for definition in definitions:
        if not _SITE_PATTERN.fullmatch(definition.site):
            raise ValueError(f"invalid site id: {definition.site}")
        if definition.site in site_ids:
            raise ValueError(f"duplicate site id: {definition.site}")
        site_ids.add(definition.site)
        if not definition.credential_fields:
            raise ValueError(f"site has no credential fields: {definition.site}")
        if not definition.checker_module or not definition.checker_class:
            raise ValueError(f"site has no checker declaration: {definition.site}")
        if len(definition.qinglong_cron.split()) != 5:
            raise ValueError(f"invalid Qinglong cron for site: {definition.site}")

        field_names: set[str] = set()
        for field in definition.credential_fields:
            if not field.name or field.name in field_names:
                raise ValueError(f"duplicate or empty credential field: {definition.site}")
            field_names.add(field.name)
            if not _ENV_KEY_PATTERN.fullmatch(field.env_key):
                raise ValueError(f"invalid environment key: {field.env_key}")
        if not _ENV_KEY_PATTERN.fullmatch(definition.base_url_key):
            raise ValueError(f"invalid environment key: {definition.base_url_key}")
        for key in definition.config_keys:
            if key in config_keys:
                raise ValueError(f"duplicate site configuration key: {key}")
            config_keys.add(key)


validate_site_definitions()

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
