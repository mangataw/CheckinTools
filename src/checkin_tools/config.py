"""Environment-backed configuration with strict validation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when one or more configuration values are invalid."""


@dataclass(frozen=True, slots=True)
class FulibaAccount:
    username: str
    cookie: str


@dataclass(frozen=True, slots=True)
class V2exAccount:
    username: str
    cookie: str


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
    javbus_cookies: tuple[str, ...]
    fuliba_accounts: tuple[FulibaAccount, ...]
    v2ex_accounts: tuple[V2exAccount, ...]
    javbus_base_url: str
    fuliba_base_url: str
    v2ex_base_url: str
    timeout_seconds: float
    retries: int
    dingtalk: DingTalkConfig | None
    feishu: FeishuConfig | None
    notify_channel: str
    notify_mode: str

    def secrets(self) -> tuple[str, ...]:
        values = [*self.javbus_cookies]
        for account in self.fuliba_accounts:
            values.extend((account.username, account.cookie))
        for account in self.v2ex_accounts:
            values.extend((account.username, account.cookie))
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


def load_config(
    environ: Mapping[str, str] | None = None, *, load_local_dotenv: bool = True
) -> AppConfig:
    if environ is None:
        if load_local_dotenv:
            load_dotenv()
        environ = os.environ

    usernames = _lines(environ.get("FULIBA_USERNAMES"))
    fuliba_cookies = _lines(environ.get("FULIBA_COOKIES"))
    if len(usernames) != len(fuliba_cookies):
        raise ConfigError("FULIBA_USERNAMES and FULIBA_COOKIES must have the same line count")

    v2ex_usernames = _lines(environ.get("V2EX_USERNAMES"))
    v2ex_cookies = _lines(environ.get("V2EX_COOKIES"))
    if len(v2ex_usernames) != len(v2ex_cookies):
        raise ConfigError("V2EX_USERNAMES and V2EX_COOKIES must have the same line count")

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
        javbus_cookies=_lines(environ.get("JAVBUS_COOKIES")),
        fuliba_accounts=tuple(
            FulibaAccount(username, cookie)
            for username, cookie in zip(usernames, fuliba_cookies, strict=True)
        ),
        v2ex_accounts=tuple(
            V2exAccount(username, cookie)
            for username, cookie in zip(v2ex_usernames, v2ex_cookies, strict=True)
        ),
        javbus_base_url=validate_base_url(
            environ.get("JAVBUS_BASE_URL", "https://www.javbus.com"), "JAVBUS_BASE_URL"
        ),
        fuliba_base_url=validate_base_url(
            environ.get("FULIBA_BASE_URL", "https://www.wnflb2023.com"), "FULIBA_BASE_URL"
        ),
        v2ex_base_url=validate_base_url(
            environ.get("V2EX_BASE_URL", "https://www.v2ex.com"), "V2EX_BASE_URL"
        ),
        timeout_seconds=timeout,
        retries=retries,
        dingtalk=DingTalkConfig(*dingtalk_values) if dingtalk_values else None,
        feishu=FeishuConfig(*feishu_values) if feishu_values else None,
        notify_channel=notify_channel,
        notify_mode=notify_mode,
    )
