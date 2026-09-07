"""Built-in checker registration."""

from checkin_tools.checkers.fuliba import FulibaChecker
from checkin_tools.checkers.javbus import JavBusChecker
from checkin_tools.checkers.v2ex import V2exChecker
from checkin_tools.site_catalog import SITE_IDS

_CHECKER_TYPES = {
    JavBusChecker.site: JavBusChecker,
    FulibaChecker.site: FulibaChecker,
    V2exChecker.site: V2exChecker,
}


def build_checkers(config):
    if set(_CHECKER_TYPES) != set(SITE_IDS):
        raise RuntimeError("checker registrations do not match the site catalog")
    return [_CHECKER_TYPES[site](config) for site in SITE_IDS]


__all__ = ["FulibaChecker", "JavBusChecker", "V2exChecker", "build_checkers"]
