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
    site_definition,
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
