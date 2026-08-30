import re
from pathlib import Path


def workflow(name):
    return (Path(__file__).parents[1] / ".github" / "workflows" / name).read_text(
        encoding="utf-8"
    )


def test_all_actions_are_pinned_to_full_commit_shas():
    for name in ("ci.yml", "checkin.yml"):
        contents = workflow(name)
        uses = re.findall(r"uses:\s*([^\s#]+)", contents)
        assert uses
        assert all(re.search(r"@[0-9a-f]{40}$", item) for item in uses)


def test_ci_never_references_checkin_or_notification_secrets():
    contents = workflow("ci.yml")
    for secret in (
        "JAVBUS_COOKIES",
        "FULIBA_USERNAMES",
        "FULIBA_COOKIES",
        "V2EX_USERNAMES",
        "V2EX_COOKIES",
        "DINGTALK_ACCESS_TOKEN",
        "FEISHU_WEBHOOK",
    ):
        assert secret not in contents
    assert "contents: read" in contents


def test_checkin_schedule_and_manual_sites_are_present():
    contents = workflow("checkin.yml")
    assert 'cron: "30 17 * * *"' in contents
    assert 'cron: "30 0 * * *"' in contents
    assert "RANDOM % 1801" in contents
    assert "--state-file .checkin-state.json" in contents
    assert "checkin-state-${{ env.CHECKIN_DATE }}-" in contents
    assert "workflow_dispatch:" in contents
    assert all(f"- {site}" in contents for site in ("all", "javbus", "fuliba", "v2ex"))
    assert "V2EX_USERNAMES: ${{ secrets.V2EX_USERNAMES }}" in contents
    assert "V2EX_COOKIES: ${{ secrets.V2EX_COOKIES }}" in contents
    assert "contents: read" in contents
