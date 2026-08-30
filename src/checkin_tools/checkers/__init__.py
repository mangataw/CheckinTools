"""Built-in checker registration."""

from checkin_tools.checkers.fuliba import FulibaChecker
from checkin_tools.checkers.javbus import JavBusChecker
from checkin_tools.checkers.v2ex import V2exChecker


def build_checkers(config):
    return [JavBusChecker(config), FulibaChecker(config), V2exChecker(config)]


__all__ = ["FulibaChecker", "JavBusChecker", "V2exChecker", "build_checkers"]
