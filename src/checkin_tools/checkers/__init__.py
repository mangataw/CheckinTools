"""Built-in checker loading from the trusted site catalog."""

from __future__ import annotations

from importlib import import_module

from checkin_tools.interfaces import Checker
from checkin_tools.site_catalog import SITE_DEFINITIONS, SiteDefinition


def _checker_type(definition: SiteDefinition) -> type[Checker]:
    module = import_module(definition.checker_module)
    checker_type = getattr(module, definition.checker_class, None)
    if not isinstance(checker_type, type) or not issubclass(checker_type, Checker):
        raise RuntimeError(f"invalid checker declaration for {definition.site}")
    if checker_type.site != definition.site:
        raise RuntimeError(f"checker identity does not match catalog for {definition.site}")
    return checker_type


def build_checkers(config):
    return [_checker_type(definition)(config) for definition in SITE_DEFINITIONS]


__all__ = ["build_checkers"]
