"""Initialize CheckinTools after a Qinglong subscription update; not a cron task."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_TEMPLATE = REPO_ROOT / "qinglong" / "checkin-tools.env"
CONFIG_FILE = Path("/ql/data/config/checkin-tools.env")


def ensure_config(template: Path = CONFIG_TEMPLATE, destination: Path = CONFIG_FILE) -> bool:
    """Copy the public template once without overwriting an existing private config."""
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        print(f"保留已有配置：{destination}")
        return False
    try:
        with os.fdopen(descriptor, "wb") as config_file:
            config_file.write(template.read_bytes())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    print(f"已创建配置：{destination}")
    return True


def install_project(repo_root: Path = REPO_ROOT) -> int:
    """Install the package and its declared dependencies into Qinglong's Python."""
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "-e",
        str(repo_root),
    ]
    print("正在安装或检查 CheckinTools Python 依赖……")
    return subprocess.run(command, check=False).returncode


def main() -> int:
    # This standalone bootstrap runs before pip can enforce pyproject.toml.
    if sys.version_info < (3, 12):  # noqa: UP036
        print("CheckinTools 需要 Python 3.12 或更高版本。", file=sys.stderr)
        return 2
    old_umask = os.umask(0o077)
    try:
        ensure_config()
        code = install_project()
        if code:
            print("Python 依赖安装失败，请查看上方 pip 日志。", file=sys.stderr)
            return code
        print("CheckinTools 青龙初始化完成。")
        return 0
    except OSError as exc:
        print(f"青龙初始化失败：{exc}", file=sys.stderr)
        return 2
    finally:
        os.umask(old_umask)


if __name__ == "__main__":
    raise SystemExit(main())
