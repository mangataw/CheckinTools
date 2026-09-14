import json

import pytest

from checkin_tools.contracts import CheckinResult, NotificationResult, ResultStatus, RunReport
from checkin_tools.state import (
    DailyState,
    StateError,
    account_state_key,
    load_daily_state,
    save_daily_state,
)


def test_missing_or_old_state_starts_a_clean_day(tmp_path):
    path = tmp_path / "state.json"
    assert load_daily_state(path, "2026-08-29") == DailyState("2026-08-29")
    path.write_text(
        '{"version":2,"date":"2026-08-28","terminal_accounts":["site:account-1"]}'
    )
    assert not load_daily_state(path, "2026-08-29").terminal_accounts


def test_legacy_state_is_invalidated_after_terminal_semantics_change(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"date":"2026-08-29","terminal_accounts":["site:account-1"]}')
    assert not load_daily_state(path, "2026-08-29").terminal_accounts


def test_state_records_only_terminal_results_and_round_trips(tmp_path):
    state = DailyState("2026-08-29")
    state.update(
        RunReport(
            results=[
                CheckinResult("site", "account-1", ResultStatus.SUCCESS, "done", 0.1),
                CheckinResult(
                    "site", "account-4", ResultStatus.ALREADY_DONE, "already", 0.1
                ),
                CheckinResult(
                    "site", "account-2", ResultStatus.FAILED, "network", 0.1, retryable=True
                ),
                CheckinResult("site", "account-3", ResultStatus.FAILED, "invalid", 0.1),
            ]
        )
    )
    assert state.terminal_accounts == {"site:account-1", "site:account-4"}
    path = tmp_path / "state.json"
    save_daily_state(path, state)
    assert load_daily_state(path, "2026-08-29") == state
    payload = json.loads(path.read_text())
    assert payload["version"] == 2
    assert payload["date"] == "2026-08-29"


def test_notification_failure_does_not_retry_a_successful_checkin():
    state = DailyState("2026-08-29")
    state.update(
        RunReport(
            results=[
                CheckinResult("site", "account-1", ResultStatus.SUCCESS, "done", 0.1)
            ],
            notifications=[NotificationResult("dingtalk", False, "network failure")],
        )
    )
    assert state.terminal_accounts == {"site:account-1"}


def test_account_state_key_is_stable_scoped_and_anonymous():
    identity = ("private-user", "private-cookie")
    first = account_state_key("site", identity)
    assert first == account_state_key("site", identity)
    assert first != account_state_key("other-site", identity)
    assert first != account_state_key("site", ("private-user", "new-cookie"))
    assert first.startswith("site:account-")
    assert "private-user" not in first
    assert "private-cookie" not in first


def test_state_prefers_explicit_stable_key_for_terminal_result():
    stable_key = account_state_key("site", ("user", "cookie"))
    state = DailyState("2026-09-07")
    state.update(
        RunReport(
            results=[
                CheckinResult(
                    "site",
                    "account-1",
                    ResultStatus.SUCCESS,
                    "done",
                    0.1,
                    state_key=stable_key,
                )
            ]
        )
    )
    assert state.terminal_accounts == {stable_key}


@pytest.mark.parametrize(
    "contents",
    [
        "not-json",
        '{"version":2,"date":"2026-08-29","terminal_accounts":"wrong"}',
        "[]",
    ],
)
def test_invalid_state_fails_closed(tmp_path, contents):
    path = tmp_path / "state.json"
    path.write_text(contents)
    with pytest.raises(StateError):
        load_daily_state(path, "2026-08-29")
