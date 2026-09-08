import pytest

from checkin_tools.checkers import build_checkers
from checkin_tools.checkers.fuliba import FulibaChecker
from checkin_tools.checkers.javbus import JavBusChecker
from checkin_tools.checkers.v2ex import V2exChecker
from checkin_tools.config import APP_CONFIG_KEYS, load_config
from checkin_tools.site_catalog import (
    SITE_CONFIG_KEYS,
    SITE_DEFINITIONS,
    SITE_IDS,
    CredentialField,
    SiteDefinition,
    site_definition,
    validate_site_definitions,
)


def test_site_catalog_has_unique_ids_and_configuration_keys():
    assert len(SITE_IDS) == len(set(SITE_IDS))
    assert {
        key for definition in SITE_DEFINITIONS for key in definition.config_keys
    } == SITE_CONFIG_KEYS
    assert SITE_CONFIG_KEYS <= APP_CONFIG_KEYS


def test_checkers_use_catalog_identity():
    checker_types = (JavBusChecker, FulibaChecker, V2exChecker)
    assert tuple(checker.site for checker in checker_types) == SITE_IDS
    assert tuple(checker.display_name for checker in checker_types) == tuple(
        definition.display_name for definition in SITE_DEFINITIONS
    )
    checkers = build_checkers(load_config({}, load_local_dotenv=False))
    assert tuple(checker.site for checker in checkers) == SITE_IDS


def test_site_definition_rejects_unknown_site():
    with pytest.raises(ValueError, match="unknown site"):
        site_definition("unknown")


def test_catalog_validation_rejects_invalid_or_duplicate_declarations():
    definition = SITE_DEFINITIONS[0]
    duplicate_key = SiteDefinition(
        site="example",
        display_name="Example",
        summary="Example",
        documentation="docs/example.md",
        checker_module="checkin_tools.checkers.example",
        checker_class="ExampleChecker",
        qinglong_task_name="Example",
        credential_fields=(
            CredentialField("cookie", definition.credential_keys[0], "Cookie", "x", "x"),
        ),
        base_url_key="EXAMPLE_BASE_URL",
        default_base_url="https://example.com",
    )
    with pytest.raises(ValueError, match="duplicate site configuration key"):
        validate_site_definitions((definition, duplicate_key))

    invalid_id = SiteDefinition(
        site="Invalid-Site",
        display_name="Invalid",
        summary="Invalid",
        documentation="docs/invalid.md",
        checker_module="invalid",
        checker_class="InvalidChecker",
        qinglong_task_name="Invalid",
        credential_fields=(CredentialField("cookie", "INVALID_COOKIE", "Cookie", "x", "x"),),
        base_url_key="INVALID_BASE_URL",
        default_base_url="https://example.com",
    )
    with pytest.raises(ValueError, match="invalid site id"):
        validate_site_definitions((invalid_id,))
