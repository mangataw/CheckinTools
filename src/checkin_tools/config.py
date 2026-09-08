"""Environment-backed configuration with strict validation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv

from checkin_tools.site_catalog import (
    SITE_CONFIG_KEYS,
    SITE_DEFINITIONS,
    SiteDefinition,
    site_definition,
)

APP_CONFIG_KEYS = SITE_CONFIG_KEYS | {
    "CHECKIN_TIMEOUT_SECONDS",
    "CHECKIN_RETRIES",
    "DINGTALK_ACCESS_TOKEN",
    "DINGTALK_SECRET",
    "FEISHU_WEBHOOK",
    "FEISHU_SECRET",
    "CHECKIN_NOTIFY_CHANNEL",
    "CHECKIN_NOTIFY_MODE",
}


class ConfigError(ValueError):
    """Raised when one or more configuration values are invalid."""


@dataclass(frozen=True, slots=True)
class SiteAccount:
    """One account whose named credential values follow its site declaration."""

    fields: tuple[tuple[str, str], ...]

    @classmethod
    def create(cls, **values: str) -> SiteAccount:
        return cls(tuple(values.items()))

    def value(self, name: str) -> str:
        try:
            return dict(self.fields)[name]
        except KeyError as exc:
            raise AttributeError(f"account has no {name!r} field") from exc

    @property
    def username(self) -> str:
        return self.value("username")

    @property
    def cookie(self) -> str:
        return self.value("cookie")

    def secret_values(self) -> tuple[str, ...]:
        return tuple(value for _, value in self.fields if value)


def FulibaAccount(username: str, cookie: str) -> SiteAccount:
    """Build a legacy Fuliba account value."""
    return SiteAccount.create(username=username, cookie=cookie)


def V2exAccount(username: str, cookie: str) -> SiteAccount:
    """Build a legacy V2EX account value."""
    return SiteAccount.create(username=username, cookie=cookie)


@dataclass(frozen=True, slots=True)
class SiteConfig:
    definition: SiteDefinition
    accounts: tuple[SiteAccount, ...]
    base_url: str


@dataclass(frozen=True, slots=True)
class DingTalkConfig:
    access_token: str
    secret: str


@dataclass(frozen=True, slots=True)
class FeishuConfig:
    webhook: str
    secret: str


@dataclass(frozen=True, slots=True)
class AppConfig:
    sites: tuple[SiteConfig, ...]
    timeout_seconds: float
    retries: int
    dingtalk: DingTalkConfig | None
    feishu: FeishuConfig | None
    notify_channel: str
    notify_mode: str

    def site(self, site: str) -> SiteConfig:
        try:
            return next(config for config in self.sites if config.definition.site == site)
        except StopIteration as exc:
            raise ValueError(f"unknown site: {site}") from exc

    @property
    def javbus_cookies(self) -> tuple[str, ...]:
        return tuple(account.cookie for account in self.site("javbus").accounts)

    @property
    def fuliba_accounts(self) -> tuple[SiteAccount, ...]:
        return self.site("fuliba").accounts

    @property
    def v2ex_accounts(self) -> tuple[SiteAccount, ...]:
        return self.site("v2ex").accounts

    @property
    def javbus_base_url(self) -> str:
        return self.site("javbus").base_url

    @property
    def fuliba_base_url(self) -> str:
        return self.site("fuliba").base_url

    @property
    def v2ex_base_url(self) -> str:
        return self.site("v2ex").base_url

    def secrets(self) -> tuple[str, ...]:
        values = [
            value
            for site in self.sites
            for account in site.accounts
            for value in account.secret_values()
        ]
        if self.dingtalk:
            values.extend((self.dingtalk.access_token, self.dingtalk.secret))
        if self.feishu:
            values.extend((self.feishu.webhook, self.feishu.secret))
        return tuple(value for value in values if value)


def _lines(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.replace("\\n", "\n").splitlines() if part.strip())


def validate_base_url(value: str, name: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ConfigError(f"{name} must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError(f"{name} must not contain credentials, query parameters, or fragments")
    if parsed.path not in ("", "/"):
        raise ConfigError(f"{name} must not contain a path")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{parsed.hostname.lower()}{port}"


def _paired_channel(
    env: Mapping[str, str], first: str, second: str, label: str
) -> tuple[str, str] | None:
    values = (env.get(first, "").strip(), env.get(second, "").strip())
    if bool(values[0]) != bool(values[1]):
        raise ConfigError(f"{label} requires both {first} and {second}")
    return values if all(values) else None


def _load_site_config(
    definition: SiteDefinition,
    environ: Mapping[str, str],
    *,
    enabled: bool,
) -> SiteConfig:
    columns = [
        _lines(environ.get(field.env_key)) if enabled else ()
        for field in definition.credential_fields
    ]
    lengths = {len(column) for column in columns}
    if len(lengths) > 1:
        keys = " and ".join(definition.credential_keys)
        raise ConfigError(f"{keys} must have the same line count")

    accounts = tuple(
        SiteAccount(
            tuple(
                (field.name, column[index])
                for field, column in zip(definition.credential_fields, columns, strict=True)
            )
        )
        for index in range(len(columns[0]) if columns else 0)
    )
    raw_url = environ.get(definition.base_url_key) if enabled else None
    return SiteConfig(
        definition=definition,
        accounts=accounts,
        base_url=validate_base_url(
            raw_url or definition.default_base_url,
            definition.base_url_key,
        ),
    )


def load_config(
    environ: Mapping[str, str] | None = None,
    *,
    load_local_dotenv: bool = True,
    selected_site: str | None = None,
) -> AppConfig:
    if environ is None:
        if load_local_dotenv:
            load_dotenv()
        environ = os.environ

    try:
        selected = site_definition(selected_site) if selected_site else None
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    site_configs = tuple(
        _load_site_config(
            definition,
            environ,
            enabled=selected is None or selected.site == definition.site,
        )
        for definition in SITE_DEFINITIONS
    )

    try:
        timeout = float(environ.get("CHECKIN_TIMEOUT_SECONDS", "20"))
        retries = int(environ.get("CHECKIN_RETRIES", "2"))
    except ValueError as exc:
        raise ConfigError("timeout and retries must be numeric") from exc
    if timeout <= 0 or retries < 0 or retries > 10:
        raise ConfigError("timeout must be positive and retries must be between 0 and 10")

    dingtalk_values = _paired_channel(
        environ, "DINGTALK_ACCESS_TOKEN", "DINGTALK_SECRET", "DingTalk"
    )
    if dingtalk_values:
        access_token = dingtalk_values[0]
        if (
            access_token.lower().startswith(("http://", "https://"))
            or "access_token=" in access_token
        ):
            raise ConfigError(
                "DINGTALK_ACCESS_TOKEN must contain only the value after access_token="
            )
    feishu_values = _paired_channel(environ, "FEISHU_WEBHOOK", "FEISHU_SECRET", "Feishu")
    if feishu_values:
        parsed_webhook = urlsplit(feishu_values[0])
        if (
            parsed_webhook.scheme != "https"
            or not parsed_webhook.hostname
            or parsed_webhook.username
            or parsed_webhook.password
            or parsed_webhook.query
            or parsed_webhook.fragment
        ):
            raise ConfigError("FEISHU_WEBHOOK must be a safe HTTPS URL")

    notify_channel = (environ.get("CHECKIN_NOTIFY_CHANNEL") or "auto").strip().lower()
    if notify_channel not in {"auto", "all", "dingtalk", "feishu"}:
        raise ConfigError("CHECKIN_NOTIFY_CHANNEL must be auto, all, dingtalk, or feishu")
    if notify_channel == "dingtalk" and not dingtalk_values:
        raise ConfigError("CHECKIN_NOTIFY_CHANNEL selects DingTalk but it is not configured")
    if notify_channel == "feishu" and not feishu_values:
        raise ConfigError("CHECKIN_NOTIFY_CHANNEL selects Feishu but it is not configured")
    notify_mode = (environ.get("CHECKIN_NOTIFY_MODE") or "summary").strip().lower()
    if notify_mode not in {"summary", "individual"}:
        raise ConfigError("CHECKIN_NOTIFY_MODE must be summary or individual")

    return AppConfig(
        sites=site_configs,
        timeout_seconds=timeout,
        retries=retries,
        dingtalk=DingTalkConfig(*dingtalk_values) if dingtalk_values else None,
        feishu=FeishuConfig(*feishu_values) if feishu_values else None,
        notify_channel=notify_channel,
        notify_mode=notify_mode,
    )
