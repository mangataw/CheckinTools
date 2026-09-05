"""
cron: 30 0,8 * * *
new Env('CheckinTools - JavBus 签到');
"""

from checkin_base import run_site

if __name__ == "__main__":
    raise SystemExit(run_site("javbus"))
