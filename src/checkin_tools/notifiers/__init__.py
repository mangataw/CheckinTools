"""Built-in notifier registration."""

from checkin_tools.notifiers.dingtalk import DingTalkNotifier
from checkin_tools.notifiers.feishu import FeishuNotifier


def build_notifiers(config, selection: str | None = None):
    available = {}
    if config.dingtalk:
        available["dingtalk"] = DingTalkNotifier(
            config.dingtalk, config.timeout_seconds, config.retries
        )
    if config.feishu:
        available["feishu"] = FeishuNotifier(
            config.feishu, config.timeout_seconds, config.retries
        )

    selection = selection or config.notify_channel
    if selection == "all":
        return list(available.values())
    if selection == "auto":
        preferred = "dingtalk" if "dingtalk" in available else "feishu"
        return [available[preferred]] if preferred in available else []
    return [available[selection]] if selection in available else []


__all__ = ["DingTalkNotifier", "FeishuNotifier", "build_notifiers"]
