"""
cron: 30 0,8 * * *
new Env('CheckinTools 每日签到');
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_CONFIG_FILE = Path("/ql/data/config/checkin-tools.env")
CONFIG_KEYS = {
    "JAVBUS_COOKIES",
    "FULIBA_USERNAMES",
    "FULIBA_COOKIES",
    "V2EX_USERNAMES",
    "V2EX_COOKIES",
    "JAVBUS_BASE_URL",
    "FULIBA_BASE_URL",
    "V2EX_BASE_URL",
    "CHECKIN_TIMEOUT_SECONDS",
    "CHECKIN_RETRIES",
    "DINGTALK_ACCESS_TOKEN",
    "DINGTALK_SECRET",
    "FEISHU_WEBHOOK",
    "FEISHU_SECRET",
    "CHECKIN_NOTIFY_CHANNEL",
    "CHECKIN_NOTIFY_MODE",
    "CHECKIN_QINGLONG_DATA_DIR",
}
CONFIG_TEMPLATE = """# CheckinTools 青龙集中配置
# 本文件只保存在 /ql/data，不要提交到 Git。修改后下次任务运行自动生效。
# 多账号使用字面量 \\n 分隔；Cookie 建议使用单引号，保留其中的双引号和符号。

# ── JavBus ─────────────────────────────────────────────────────────────
# 单账号：JAVBUS_COOKIES='完整 Cookie'
# 多账号：JAVBUS_COOKIES='账号1 Cookie\\n账号2 Cookie'
JAVBUS_COOKIES=''

# ── 福利吧 ─────────────────────────────────────────────────────────────
# 用户名与 Cookie 必须按相同行号一一对应。
FULIBA_USERNAMES=''
FULIBA_COOKIES=''

# ── V2EX ───────────────────────────────────────────────────────────────
# 用户名与 Cookie 必须按相同行号一一对应。
V2EX_USERNAMES=''
V2EX_COOKIES=''

# ── 站点地址 ───────────────────────────────────────────────────────────
JAVBUS_BASE_URL='https://www.javbus.com'
FULIBA_BASE_URL='https://www.wnflb2023.com'
V2EX_BASE_URL='https://www.v2ex.com'

# ── 网络请求 ───────────────────────────────────────────────────────────
CHECKIN_TIMEOUT_SECONDS='20'
CHECKIN_RETRIES='2'

# ── 通知 ───────────────────────────────────────────────────────────────
# 钉钉和飞书都要求成对填写；不需要的渠道保持为空。
DINGTALK_ACCESS_TOKEN=''
DINGTALK_SECRET=''
FEISHU_WEBHOOK=''
FEISHU_SECRET=''
# auto：自动选择；all：全部渠道；也可填 dingtalk 或 feishu。
CHECKIN_NOTIFY_CHANNEL='auto'
# summary：每个站点一条汇总；individual：每个账号一条。
CHECKIN_NOTIFY_MODE='summary'

# ── 青龙持久化状态 ─────────────────────────────────────────────────────
CHECKIN_QINGLONG_DATA_DIR='/ql/data/checkin-tools'
"""


def _config_path(environ: Mapping[str, str]) -> Path:
    path = Path(environ.get("CHECKIN_QINGLONG_CONFIG", str(DEFAULT_CONFIG_FILE)))
    if not path.is_absolute():
        raise RuntimeError("CHECKIN_QINGLONG_CONFIG 必须是绝对路径")
    return path


def _create_config_template(path: Path) -> bool:
    """Create the complete private template once; never overwrite user values."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as config_file:
        config_file.write(CONFIG_TEMPLATE)
    return True


def _load_settings(environ: Mapping[str, str]) -> tuple[Path, dict[str, str]] | None:
    path = _config_path(environ)
    if _create_config_template(path):
        print(f"已创建青龙配置模板：{path}\n请填写后重新运行任务。")
        return None
    if not path.is_file():
        raise RuntimeError("青龙配置路径不是普通文件")

    from dotenv import dotenv_values

    parsed = dotenv_values(path)
    unknown = sorted(set(parsed) - CONFIG_KEYS)
    if unknown:
        raise RuntimeError(f"配置文件包含未知参数：{', '.join(unknown)}")
    if any(value is None for value in parsed.values()):
        raise RuntimeError("配置文件存在缺少值或无法解析的参数")
    return path, {key: value or "" for key, value in parsed.items()}


def _add_source_path() -> None:
    """Load the src-layout package from the repository pulled by Qinglong."""
    script_dir = Path(__file__).resolve().parent
    candidates = [script_dir / "src", script_dir.parent / "src"]
    for qinglong_root in (Path("/ql/data/repo"), Path("/ql/data/scripts")):
        if qinglong_root.is_dir():
            candidates.extend(qinglong_root.glob("*/src"))
    for candidate in candidates:
        if (candidate / "checkin_tools").is_dir():
            sys.path.insert(0, str(candidate))
            return
    raise RuntimeError("订阅缺少 src 目录；请拉取完整仓库，或在订阅中把 src 设为依赖文件")


def _configured_sites(environ: Mapping[str, str]) -> list[str]:
    sites = []
    if environ.get("JAVBUS_COOKIES", "").strip():
        sites.append("javbus")
    if environ.get("FULIBA_USERNAMES", "").strip() or environ.get("FULIBA_COOKIES", "").strip():
        sites.append("fuliba")
    if environ.get("V2EX_USERNAMES", "").strip() or environ.get("V2EX_COOKIES", "").strip():
        sites.append("v2ex")
    return sites


def _state_date(site: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    zone = UTC if site == "v2ex" else ZoneInfo("Asia/Shanghai")
    return now.astimezone(zone).date().isoformat()


@contextmanager
def _single_instance(data_dir: Path):
    if os.name == "nt":
        yield
        return
    import fcntl

    lock_path = data_dir / "checkin.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _run_cli(arguments: list[str], settings: Mapping[str, str]) -> int:
    from checkin_tools.cli import main

    return main(arguments, environ=settings, load_local_dotenv=False)


def main() -> int:
    old_umask = os.umask(0o077)
    try:
        loaded = _load_settings(os.environ)
        if loaded is None:
            return 2
        config_path, settings = loaded
        sites = _configured_sites(settings)
        if not sites:
            print(f"未配置任何站点账号，请编辑：{config_path}", file=sys.stderr)
            return 2

        data_dir = Path(settings.get("CHECKIN_QINGLONG_DATA_DIR", "/ql/data/checkin-tools"))
        if not data_dir.is_absolute():
            raise RuntimeError("CHECKIN_QINGLONG_DATA_DIR 必须是绝对路径")
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        _add_source_path()
        try:
            with _single_instance(data_dir):
                codes = []
                for site in sites:
                    state_file = data_dir / f"{site}-state.json"
                    codes.append(
                        _run_cli(
                            [
                                "run",
                                "--site",
                                site,
                                "--state-file",
                                str(state_file),
                                "--state-date",
                                _state_date(site),
                            ],
                            settings,
                        )
                    )
                return 1 if 1 in codes else 2 if 2 in codes else 0
        except BlockingIOError:
            print("已有 CheckinTools 青龙任务正在运行，本次跳过。", file=sys.stderr)
            return 3
    except (ImportError, OSError, RuntimeError) as exc:
        print(f"青龙运行环境错误：{exc}", file=sys.stderr)
        return 2
    finally:
        os.umask(old_umask)


if __name__ == "__main__":
    raise SystemExit(main())
