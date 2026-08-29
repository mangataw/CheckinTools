"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging

from checkin_tools.config import ConfigError, load_config
from checkin_tools.security import configure_logging, register_ci_masks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="checkin-tools")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-config")
    run = commands.add_parser("run")
    run.add_argument("--site", choices=("all", "javbus", "fuliba"), default="all")
    run.add_argument("--no-notify", action="store_true")
    notify = commands.add_parser("notify-test")
    notify.add_argument("--channel", choices=("all", "dingtalk", "feishu"), default="all")
    return parser


def _components(config):
    from checkin_tools.checkers import build_checkers
    from checkin_tools.notifiers import build_notifiers

    return build_checkers(config), build_notifiers(config)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config()
    except ConfigError as exc:
        configure_logging()
        logging.error("invalid configuration: %s", exc)
        return 2
    configure_logging(config.secrets())
    register_ci_masks(config.secrets())
    checkers, notifiers = _components(config)

    if args.command == "validate-config":
        if not any(checker.accounts for checker in checkers):
            logging.error("configuration is valid but no site accounts are configured")
            return 2
        logging.info("configuration is valid")
        return 0

    from checkin_tools.models import RunReport
    from checkin_tools.runner import Runner

    if args.command == "notify-test":
        chosen = (
            notifiers
            if args.channel == "all"
            else [notifier for notifier in notifiers if notifier.channel == args.channel]
        )
        if not chosen:
            logging.error("requested notification channel is not configured")
            return 2
        report = RunReport()
        failed = False
        for notifier in chosen:
            try:
                notifier.send(report)
                logging.info("%s notification test sent", notifier.channel)
            except Exception as exc:
                logging.error("%s notification test failed: %s", notifier.channel, exc)
                failed = True
        return 1 if failed else 0

    return Runner(checkers, notifiers, config.secrets()).run(
        args.site, notify=not args.no_notify
    ).exit_code
