"""Canonical metadata for built-in check-in sites."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SiteDefinition:
    site: str
    display_name: str
    qinglong_task_name: str
    credential_keys: tuple[str, ...]
    base_url_key: str
    default_base_url: str

    @property
    def config_keys(self) -> tuple[str, ...]:
        return (*self.credential_keys, self.base_url_key)


SITE_DEFINITIONS = (
    SiteDefinition(
        site="javbus",
        display_name="JavBus",
        qinglong_task_name="CheckinTools - JavBus 签到",
        credential_keys=("JAVBUS_COOKIES",),
        base_url_key="JAVBUS_BASE_URL",
        default_base_url="https://www.javbus.com",
    ),
    SiteDefinition(
        site="fuliba",
        display_name="福利吧",
        qinglong_task_name="CheckinTools - 福利吧签到",
        credential_keys=("FULIBA_USERNAMES", "FULIBA_COOKIES"),
        base_url_key="FULIBA_BASE_URL",
        default_base_url="https://www.wnflb2023.com",
    ),
    SiteDefinition(
        site="v2ex",
        display_name="V2EX",
        qinglong_task_name="CheckinTools - V2EX 签到",
        credential_keys=("V2EX_USERNAMES", "V2EX_COOKIES"),
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
