"""Non-sensitive daily state used to avoid duplicate scheduled check-ins."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from checkin_tools.models import RunReport


class StateError(ValueError):
    pass


@dataclass(slots=True)
class DailyState:
    date: str
    terminal_accounts: set[str] = field(default_factory=set)

    def update(self, report: RunReport) -> None:
        self.terminal_accounts.update(
            f"{result.site}:{result.account}"
            for result in report.results
            if not result.retryable
        )


def load_daily_state(path: str | Path, date: str) -> DailyState:
    state_path = Path(path)
    if not state_path.exists():
        return DailyState(date)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        if payload.get("date") != date:
            return DailyState(date)
        accounts = payload.get("terminal_accounts", [])
        if not isinstance(accounts, list) or not all(isinstance(item, str) for item in accounts):
            raise StateError("daily state contains an invalid account list")
        return DailyState(date, set(accounts))
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise StateError("daily state could not be read") from exc


def save_daily_state(path: str | Path, state: DailyState) -> None:
    state_path = Path(path)
    state_path.write_text(
        json.dumps(
            {
                "date": state.date,
                "terminal_accounts": sorted(state.terminal_accounts),
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

