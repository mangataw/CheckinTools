"""Simple extension registry."""

from __future__ import annotations

from collections.abc import Iterable

from checkin_tools.interfaces import Checker, Notifier


def checker_map(checkers: Iterable[Checker]) -> dict[str, Checker]:
    result: dict[str, Checker] = {}
    for checker in checkers:
        if checker.site in result:
            raise ValueError(f"duplicate checker: {checker.site}")
        result[checker.site] = checker
    return result


def notifier_map(notifiers: Iterable[Notifier]) -> dict[str, Notifier]:
    result: dict[str, Notifier] = {}
    for notifier in notifiers:
        if notifier.channel in result:
            raise ValueError(f"duplicate notifier: {notifier.channel}")
        result[notifier.channel] = notifier
    return result

