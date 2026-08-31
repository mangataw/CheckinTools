import json

import pytest

from checkin_tools.models import CheckinResult, ResultStatus, RunReport
from checkin_tools.state import DailyState, StateError, load_daily_state, save_daily_state


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
