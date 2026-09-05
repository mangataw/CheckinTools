"""
cron: 30 0,8 * * *
new Env('CheckinTools - V2EX 签到');
"""

from checkin_task_base import run_site

if __name__ == "__main__":
    raise SystemExit(run_site("v2ex"))
