"""Load and validate the canonical static site catalog."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

_SUPPORTED_SCHEMA_VERSION = 1
_TOP_LEVEL_FIELDS = {"schema_version", "defaults", "sites"}
_DEFAULT_FIELDS = {"qinglong_cron", "state_timezone"}
_SITE_FIELDS = {
    "id",
    "display_name",
    "base_url",
    "credentials",
    "qinglong_cron",
    "state_timezone",
}
_SITE_PATTERN = re.compile(r"[a-z0-9_]+")
_CREDENTIAL_PATTERN = re.compile(r"[a-z][a-z0-9_]*")
_ENV_KEY_PATTERN = re.compile(r"[A-Z][A-Z0-9_]+")
_RESERVED_CREDENTIAL_FIELDS = _TOP_LEVEL_FIELDS | _DEFAULT_FIELDS | _SITE_FIELDS


@dataclass(frozen=True, slots=True)
class SiteDefinition:
    id: str
    display_name: str
    base_url: str
    credentials: Mapping[str, str]
    qinglong_cron: str
    state_timezone: str

    @property
    def base_url_key(self) -> str:
        return f"{self.id.upper()}_BASE_URL"

    @property
    def credential_keys(self) -> tuple[str, ...]:
        return tuple(self.credentials.values())

    @property
    def config_keys(self) -> tuple[str, ...]:
        return (*self.credential_keys, self.base_url_key)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a table")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _reject_unknown(mapping: Mapping[str, object], allowed: set[str], field: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"{field} has unknown field: {unknown[0]}")


def _validate_base_url(value: str, field: str) -> None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field} must be an HTTPS root URL") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or port is not None and not 1 <= port <= 65535
    ):
        raise ValueError(f"{field} must be an HTTPS root URL without credentials or suffixes")


def _validate_timezone(value: str, field: str) -> None:
    if value == "local":
        return
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"{field} is not local or a valid IANA timezone") from exc


def _parse_site_definitions(document: Mapping[str, object]) -> tuple[SiteDefinition, ...]:
    _reject_unknown(document, _TOP_LEVEL_FIELDS, "catalog")
    version = document.get("schema_version")
    if type(version) is not int or version != _SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {version!r}")

    defaults = _mapping(document.get("defaults"), "defaults")
    _reject_unknown(defaults, _DEFAULT_FIELDS, "defaults")
    default_cron = _string(defaults.get("qinglong_cron"), "defaults.qinglong_cron")
    default_timezone = _string(
        defaults.get("state_timezone"), "defaults.state_timezone"
    )
    if len(default_cron.split()) != 5:
        raise ValueError("defaults.qinglong_cron must contain five fields")
    _validate_timezone(default_timezone, "defaults.state_timezone")

    raw_sites = document.get("sites")
    if not isinstance(raw_sites, list) or not raw_sites:
        raise ValueError("catalog must declare at least one site")

    definitions: list[SiteDefinition] = []
    site_ids: set[str] = set()
    environment_keys: set[str] = set()
    for index, raw_site in enumerate(raw_sites):
        site = _mapping(raw_site, f"sites[{index}]")
        site_id_hint = site.get("id") if isinstance(site.get("id"), str) else index
        field = f"site {site_id_hint}"
        _reject_unknown(site, _SITE_FIELDS, field)
        site_id = _string(site.get("id"), f"{field}.id")
        field = f"site {site_id}"
        if not _SITE_PATTERN.fullmatch(site_id):
            raise ValueError(f"{field}.id must match [a-z0-9_]+")
        if site_id in site_ids:
            raise ValueError(f"duplicate site id: {site_id}")
        site_ids.add(site_id)

        display_name = _string(site.get("display_name"), f"{field}.display_name")
        base_url = _string(site.get("base_url"), f"{field}.base_url")
        _validate_base_url(base_url, f"{field}.base_url")
        cron = _string(site.get("qinglong_cron", default_cron), f"{field}.qinglong_cron")
        if len(cron.split()) != 5:
            raise ValueError(f"{field}.qinglong_cron must contain five fields")
        timezone = _string(
            site.get("state_timezone", default_timezone), f"{field}.state_timezone"
        )
        _validate_timezone(timezone, f"{field}.state_timezone")

        raw_credentials = _mapping(site.get("credentials"), f"{field}.credentials")
        if not raw_credentials:
            raise ValueError(f"{field}.credentials must contain at least one field")
        credentials: dict[str, str] = {}
        for logical_name, raw_env_key in raw_credentials.items():
            if not _CREDENTIAL_PATTERN.fullmatch(logical_name):
                raise ValueError(f"{field}.credentials has invalid field: {logical_name}")
            if logical_name in _RESERVED_CREDENTIAL_FIELDS:
                raise ValueError(
                    f"{field}.credentials.{logical_name} is reserved; "
                    f"place {logical_name} before [sites.credentials]"
                )
            env_key = _string(raw_env_key, f"{field}.credentials.{logical_name}")
            if not _ENV_KEY_PATTERN.fullmatch(env_key):
                raise ValueError(f"{field}.credentials.{logical_name} has invalid environment key")
            if env_key in environment_keys:
                raise ValueError(f"duplicate site configuration key: {env_key}")
            environment_keys.add(env_key)
            credentials[logical_name] = env_key

        base_url_key = f"{site_id.upper()}_BASE_URL"
        if base_url_key in environment_keys:
            raise ValueError(f"{field}.base_url_key conflicts with credential key: {base_url_key}")
        definitions.append(
            SiteDefinition(
                id=site_id,
                display_name=display_name,
                base_url=base_url,
                credentials=MappingProxyType(credentials),
                qinglong_cron=cron,
                state_timezone=timezone,
            )
        )

    base_url_keys: set[str] = set()
    for definition in definitions:
        if definition.base_url_key in environment_keys or definition.base_url_key in base_url_keys:
            raise ValueError(
                f"site {definition.id}.base_url_key conflicts with another configuration key: "
                f"{definition.base_url_key}"
            )
        base_url_keys.add(definition.base_url_key)
    return tuple(definitions)


def load_site_definitions(path: str | Path | None = None) -> tuple[SiteDefinition, ...]:
    """Load definitions from package data, or from a path for validation/tests."""
    if path is None:
        resource = resources.files("checkin_tools").joinpath("sites.toml")
        with resource.open("rb") as stream:
            document = tomllib.load(stream)
    else:
        with Path(path).open("rb") as stream:
            document = tomllib.load(stream)
    return _parse_site_definitions(document)


def validate_site_definitions(definitions: tuple[SiteDefinition, ...]) -> None:
    """Validate already parsed definitions used by extension-level tests."""
    if not definitions:
        raise ValueError("site catalog must not be empty")
    site_ids: set[str] = set()
    config_keys: set[str] = set()
    for definition in definitions:
        if not _SITE_PATTERN.fullmatch(definition.id):
            raise ValueError(f"invalid site id: {definition.id}")
        if definition.id in site_ids:
            raise ValueError(f"duplicate site id: {definition.id}")
        site_ids.add(definition.id)
        if not definition.credentials:
            raise ValueError(f"site has no credential fields: {definition.id}")
        _validate_base_url(definition.base_url, f"site {definition.id}.base_url")
        if len(definition.qinglong_cron.split()) != 5:
            raise ValueError(f"invalid Qinglong cron for site: {definition.id}")
        _validate_timezone(definition.state_timezone, f"site {definition.id}.state_timezone")
        for logical_name, env_key in definition.credentials.items():
            if not _CREDENTIAL_PATTERN.fullmatch(logical_name):
                raise ValueError(f"invalid credential field: {definition.id}.{logical_name}")
            if logical_name in _RESERVED_CREDENTIAL_FIELDS:
                raise ValueError(
                    f"reserved credential field: {definition.id}.{logical_name}"
                )
            if not _ENV_KEY_PATTERN.fullmatch(env_key):
                raise ValueError(f"invalid environment key: {env_key}")
        for key in definition.config_keys:
            if key in config_keys:
                raise ValueError(f"duplicate site configuration key: {key}")
            config_keys.add(key)


SITE_DEFINITIONS = load_site_definitions()
validate_site_definitions(SITE_DEFINITIONS)
SITE_IDS = tuple(definition.id for definition in SITE_DEFINITIONS)
SITE_CONFIG_KEYS = frozenset(
    key for definition in SITE_DEFINITIONS for key in definition.config_keys
)
_SITES_BY_ID = {definition.id: definition for definition in SITE_DEFINITIONS}


def site_definition(site_id: str) -> SiteDefinition:
    try:
        return _SITES_BY_ID[site_id]
    except KeyError as exc:
        raise ValueError(f"unknown site: {site_id}") from exc
