from pathlib import Path

import pytest

from checkin_tools.checkers import build_checkers
from checkin_tools.config import APP_CONFIG_KEYS, load_config
from checkin_tools.site_catalog import (
    SITE_CONFIG_KEYS,
    SITE_DEFINITIONS,
    SITE_IDS,
    SiteDefinition,
    load_site_definitions,
    site_definition,
    validate_site_definitions,
)


def write_catalog(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sites.toml"
    path.write_text(body, encoding="utf-8")
    return path


def catalog_with(site_body: str, *, defaults: str = "") -> str:
    defaults = defaults or 'qinglong_cron = "30 0,8 * * *"\nstate_timezone = "local"'
    return f"schema_version = 1\n\n[defaults]\n{defaults}\n\n{site_body}\n"


def test_packaged_catalog_has_stable_sites_defaults_and_keys():
    assert SITE_IDS == ("javbus", "fuliba", "v2ex")
    assert SITE_DEFINITIONS[0].qinglong_cron == "30 0,8 * * *"
    assert SITE_DEFINITIONS[0].state_timezone == "local"
    assert site_definition("fuliba").credentials == {
        "username": "FULIBA_USERNAMES",
        "cookie": "FULIBA_COOKIES",
    }
    assert site_definition("v2ex").qinglong_cron == "30 8,16 * * *"
    assert site_definition("v2ex").state_timezone == "UTC"
    assert {
        key for definition in SITE_DEFINITIONS for key in definition.config_keys
    } == SITE_CONFIG_KEYS
    assert SITE_CONFIG_KEYS <= APP_CONFIG_KEYS


def test_checkers_use_catalog_identity():
    checkers = build_checkers(load_config({}, load_local_dotenv=False))
    assert tuple(checker.site for checker in checkers) == SITE_IDS
    assert tuple(checker.display_name for checker in checkers) == tuple(
        definition.display_name for definition in SITE_DEFINITIONS
    )


def test_catalog_supports_any_positive_number_of_credentials(tmp_path):
    body = """
[[sites]]
id = "one"
display_name = "One"
base_url = "https://one.example"
[sites.credentials]
cookie = "ONE_COOKIE"

[[sites]]
id = "many"
display_name = "Many"
base_url = "https://many.example"
[sites.credentials]
username = "MANY_USERNAME"
password = "MANY_PASSWORD"
token = "MANY_TOKEN"
"""
    definitions = load_site_definitions(write_catalog(tmp_path, catalog_with(body)))
    assert tuple(definition.id for definition in definitions) == ("one", "many")
    assert tuple(definitions[1].credentials) == ("username", "password", "token")


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
[[sites]]
id = "same"
display_name = "One"
base_url = "https://one.example"
[sites.credentials]
cookie = "ONE_COOKIE"
[[sites]]
id = "same"
display_name = "Two"
base_url = "https://two.example"
[sites.credentials]
cookie = "TWO_COOKIE"
""",
            "duplicate site id",
        ),
        (
            """
[[sites]]
id = "Invalid-Site"
display_name = "Invalid"
base_url = "https://example.com"
[sites.credentials]
cookie = "VALID_COOKIE"
""",
            "must match",
        ),
        (
            """
[[sites]]
id = "one"
display_name = "One"
base_url = "https://one.example"
[sites.credentials]
cookie = "SHARED_COOKIE"
[[sites]]
id = "two"
display_name = "Two"
base_url = "https://two.example"
[sites.credentials]
cookie = "SHARED_COOKIE"
""",
            "duplicate site configuration key",
        ),
        (
            """
[[sites]]
id = "bad_env"
display_name = "Bad env"
base_url = "https://example.com"
[sites.credentials]
cookie = "bad-env"
""",
            "invalid environment key",
        ),
        (
            """
[[sites]]
id = "unsafe"
display_name = "Unsafe"
base_url = "https://user@example.com/path?secret=yes"
[sites.credentials]
cookie = "UNSAFE_COOKIE"
""",
            "HTTPS root URL",
        ),
        (
            """
[[sites]]
id = "unknown"
display_name = "Unknown"
base_url = "https://example.com"
typo = true
[sites.credentials]
cookie = "UNKNOWN_COOKIE"
""",
            "unknown field",
        ),
        (
            """
[[sites]]
id = "conflict"
display_name = "Conflict"
base_url = "https://example.com"
[sites.credentials]
cookie = "CONFLICT_BASE_URL"
""",
            "conflicts with credential key",
        ),
        (
            """
[[sites]]
id = "misordered"
display_name = "Misordered"
base_url = "https://example.com"
[sites.credentials]
cookie = "MISORDERED_COOKIE"
state_timezone = "UTC"
""",
            "state_timezone is reserved; place state_timezone before",
        ),
    ],
)
def test_catalog_rejects_invalid_declarations(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        load_site_definitions(write_catalog(tmp_path, catalog_with(body)))


def test_catalog_rejects_unknown_top_level_and_schema(tmp_path):
    valid_site = """
[[sites]]
id = "example"
display_name = "Example"
base_url = "https://example.com"
[sites.credentials]
    cookie = "EXAMPLE_COOKIE"
"""
    with pytest.raises(ValueError, match="unknown field"):
        load_site_definitions(
            write_catalog(
                tmp_path,
                catalog_with(valid_site).replace(
                    "schema_version = 1", "schema_version = 1\nunexpected = true"
                ),
            )
        )
    path = write_catalog(
        tmp_path,
        catalog_with(valid_site).replace("schema_version = 1", "schema_version = 2"),
    )
    with pytest.raises(ValueError, match="unsupported schema_version"):
        load_site_definitions(path)


def test_site_definition_and_manual_validation_fail_clearly():
    with pytest.raises(ValueError, match="unknown site"):
        site_definition("unknown")
    duplicate = SiteDefinition(
        id="javbus",
        display_name="Duplicate",
        base_url="https://duplicate.example",
        credentials={"cookie": "DUPLICATE_COOKIE"},
        qinglong_cron="30 0,8 * * *",
        state_timezone="local",
    )
    with pytest.raises(ValueError, match="duplicate site id"):
        validate_site_definitions((SITE_DEFINITIONS[0], duplicate))
