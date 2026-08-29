"""Built-in checker registration."""

from checkin_tools.checkers.fuliba import FulibaChecker
from checkin_tools.checkers.javbus import JavBusChecker


def build_checkers(config):
    return [JavBusChecker(config), FulibaChecker(config)]


__all__ = ["FulibaChecker", "JavBusChecker", "build_checkers"]

