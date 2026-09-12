"""Convention-based loading for checkers in the trusted site catalog."""

from __future__ import annotations

from importlib import import_module

from checkin_tools.interfaces import Checker
from checkin_tools.site_catalog import SITE_DEFINITIONS, SiteDefinition


def _checker_type(definition: SiteDefinition) -> type[Checker]:
    module_name = f"checkin_tools.checkers.{definition.id}"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise RuntimeError(
                f"checker module is missing for site {definition.id}: {module_name}"
            ) from exc
        raise
    checker_type = getattr(module, "SiteChecker", None)
    if not isinstance(checker_type, type) or not issubclass(checker_type, Checker):
        raise RuntimeError(
            f"site {definition.id} must export SiteChecker as a Checker subclass"
        )
    return checker_type


def _build_checker(config, definition: SiteDefinition) -> Checker:
    checker = _checker_type(definition)(config, definition=definition)
    if checker.site != definition.id:
        raise RuntimeError(f"checker identity does not match catalog for {definition.id}")
    return checker


def build_checkers(config):
    return [_build_checker(config, definition) for definition in SITE_DEFINITIONS]


__all__ = ["build_checkers"]
