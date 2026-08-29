from checkin_tools.interfaces import Checker, Notifier
from checkin_tools.models import CheckinResult, ResultStatus
from checkin_tools.registry import checker_map, notifier_map
from checkin_tools.runner import Runner


class FakeChecker(Checker):
    site = "fake"
    display_name = "Fake"

    def __init__(self, accounts=("ok", "fail")):
        self._accounts = accounts

    @property
    def accounts(self):
        return self._accounts

    def check(self, account, account_label):
        if account == "fail":
            raise RuntimeError("cookie=should-not-leak")
        return CheckinResult(self.site, account_label, ResultStatus.SUCCESS, "done", 0.01)


class FakeNotifier(Notifier):
    channel = "fake-channel"

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def send(self, report):
        self.calls += 1
        if self.fail:
            raise RuntimeError("secret=should-not-leak")


def test_runner_isolates_accounts_and_notifies_once():
    notifier = FakeNotifier()
    report = Runner([FakeChecker()], [notifier]).run()
    assert [result.status for result in report.results] == [
        ResultStatus.SUCCESS,
        ResultStatus.FAILED,
    ]
    assert "should-not-leak" not in report.results[1].summary
    assert notifier.calls == 1
    assert report.exit_code == 1


def test_runner_can_skip_notifications_and_reports_no_tasks():
    notifier = FakeNotifier()
    report = Runner([FakeChecker(())], [notifier]).run(notify=False)
    assert notifier.calls == 0
    assert report.exit_code == 2


def test_notification_failure_isolated():
    working = FakeNotifier()
    failing = FakeNotifier(True)
    failing.channel = "failing"
    report = Runner([FakeChecker(("ok",))], [failing, working]).run()
    assert [item.success for item in report.notifications] == [False, True]
    assert working.calls == 1
    assert "should-not-leak" not in report.notifications[0].summary
    assert report.exit_code == 1


def test_runner_redacts_configured_secrets_from_extension_errors():
    class LeakingNotifier(FakeNotifier):
        channel = "leaking"

        def send(self, report):
            raise RuntimeError("opaque-private-value")

    report = Runner(
        [FakeChecker(("ok",))], [LeakingNotifier()], ("opaque-private-value",)
    ).run()
    assert report.notifications[0].summary == "***"


def test_site_selection_and_unknown_site():
    checker = FakeChecker(("ok",))
    assert Runner([checker]).run("fake").exit_code == 0
    assert Runner([checker]).run("missing").exit_code == 2


def test_runner_skips_terminal_accounts_without_turning_run_into_failure():
    checker = FakeChecker(("ok", "ok"))
    report = Runner([checker], terminal_accounts={"fake:account-1", "fake:account-2"}).run()
    assert not report.results
    assert report.skipped_accounts == 2
    assert report.exit_code == 0


def test_individual_notification_mode_sends_one_message_per_result():
    notifier = FakeNotifier()
    report = Runner(
        [FakeChecker(("ok", "ok"))], [notifier], notification_mode="individual"
    ).run()
    assert notifier.calls == 2
    assert len(report.notifications) == 2


def test_registries_reject_duplicates():
    import pytest

    with pytest.raises(ValueError):
        checker_map([FakeChecker(), FakeChecker()])
    first, second = FakeNotifier(), FakeNotifier()
    with pytest.raises(ValueError):
        notifier_map([first, second])
