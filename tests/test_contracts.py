from checkin_tools.contracts import (
    Checker,
    CheckinResult,
    NotificationResult,
    ResultStatus,
    RunReport,
)


class ExampleChecker(Checker):
    site = "example"
    display_name = "Example"

    @property
    def accounts(self):
        return ("secret",)

    def check(self, account, account_label):
        return CheckinResult(self.site, account_label, ResultStatus.SUCCESS, "done", 0)


def test_checker_default_state_identity_remains_repr_based():
    checker = ExampleChecker()
    assert checker.state_identity("secret") == ("'secret'",)


def test_run_report_exit_code_semantics_remain_compatible():
    assert RunReport().exit_code == 2
    assert RunReport(skipped_accounts=1).exit_code == 0
    assert RunReport(
        results=[CheckinResult("site", "account", ResultStatus.SUCCESS, "done", 0)]
    ).exit_code == 0
    assert RunReport(
        results=[CheckinResult("site", "account", ResultStatus.FAILED, "failed", 0)]
    ).exit_code == 1
    assert RunReport(
        results=[CheckinResult("site", "account", ResultStatus.SUCCESS, "done", 0)],
        notifications=[NotificationResult("channel", False, "failed")],
    ).exit_code == 1
