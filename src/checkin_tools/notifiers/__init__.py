"""Built-in notifier registration."""

from checkin_tools.notifiers.dingtalk import DingTalkNotifier
from checkin_tools.notifiers.feishu import FeishuNotifier


def build_notifiers(config):
    notifiers = []
    if config.dingtalk:
        notifiers.append(
            DingTalkNotifier(config.dingtalk, config.timeout_seconds, config.retries)
        )
    if config.feishu:
        notifiers.append(FeishuNotifier(config.feishu, config.timeout_seconds, config.retries))
    return notifiers


__all__ = ["DingTalkNotifier", "FeishuNotifier", "build_notifiers"]

