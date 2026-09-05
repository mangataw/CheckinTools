"""Shared runtime for CheckinTools Qinglong tasks; this file is not a task."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_CONFIG_FILE = Path("/ql/data/config/checkin-tools.env")
SITES = {"javbus", "fuliba", "v2ex"}
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


def _config_path(environ: Mapping[str, str]) -> Path:
    path = Path(environ.get("CHECKIN_QINGLONG_CONFIG", str(DEFAULT_CONFIG_FILE)))
    if not path.is_absolute():
        raise RuntimeError("CHECKIN_QINGLONG_CONFIG 必须是绝对路径")
    return path


def _load_settings(environ: Mapping[str, str]) -> tuple[Path, dict[str, str]]:
    path = _config_path(environ)
    if not path.is_file():
        raise RuntimeError(
            f"青龙配置文件不存在：{path}；请运行带有“执行后”初始化命令的订阅"
        )

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
    candidates = [
        script_dir / "src",
        script_dir.parent / "src",
        script_dir.parent.parent / "src",
    ]
    for qinglong_root in (Path("/ql/data/repo"), Path("/ql/data/scripts")):
        if qinglong_root.is_dir():
            candidates.extend(qinglong_root.glob("*/src"))
    for candidate in candidates:
        if (candidate / "checkin_tools").is_dir():
            sys.path.insert(0, str(candidate))
            return
    raise RuntimeError("订阅目录中缺少 src/checkin_tools")


def _site_is_configured(site: str, settings: Mapping[str, str]) -> bool:
    keys = {
        "javbus": ("JAVBUS_COOKIES",),
        "fuliba": ("FULIBA_USERNAMES", "FULIBA_COOKIES"),
        "v2ex": ("V2EX_USERNAMES", "V2EX_COOKIES"),
    }[site]
    return any(settings.get(key, "").strip() for key in keys)


def _state_date(site: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    zone = timezone.utc if site == "v2ex" else ZoneInfo("Asia/Shanghai")
    return now.astimezone(zone).date().isoformat()


@contextmanager
def _single_instance(data_dir: Path, site: str):
    if os.name == "nt":
        yield
        return
    import fcntl

    lock_path = data_dir / f"{site}.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _run_cli(arguments: list[str], settings: Mapping[str, str]) -> int:
    from checkin_tools.cli import main

    return main(arguments, environ=settings, load_local_dotenv=False)


def run_site(site: str) -> int:
    """Run one site as one independently managed Qinglong task."""
    if site not in SITES:
        raise ValueError(f"unknown site: {site}")
    old_umask = os.umask(0o077)
    try:
        config_path, settings = _load_settings(os.environ)
        if not _site_is_configured(site, settings):
            print(f"{site} 未配置账号，请编辑：{config_path}", file=sys.stderr)
            return 2

        data_dir = Path(settings.get("CHECKIN_QINGLONG_DATA_DIR", "/ql/data/checkin-tools"))
        if not data_dir.is_absolute():
            raise RuntimeError("CHECKIN_QINGLONG_DATA_DIR 必须是绝对路径")
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        _add_source_path()
        try:
            with _single_instance(data_dir, site):
                return _run_cli(
                    [
                        "run",
                        "--site",
                        site,
                        "--state-file",
                        str(data_dir / f"{site}-state.json"),
                        "--state-date",
                        _state_date(site),
                    ],
                    settings,
                )
        except BlockingIOError:
            print(f"已有 {site} 青龙任务正在运行，本次跳过。", file=sys.stderr)
            return 3
    except (ImportError, OSError, RuntimeError) as exc:
        print(f"青龙运行环境错误：{exc}", file=sys.stderr)
        return 2
    finally:
        os.umask(old_umask)
