"""Initialize CheckinTools after a Qinglong subscription update; not a cron task."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_TEMPLATE = REPO_ROOT / "qinglong" / "checkin-tools.env"
CONFIG_FILE = Path("/ql/data/config/checkin-tools.env")
_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


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


def _assignment_lines(text: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line in text.splitlines():
        match = _ASSIGNMENT.match(line)
        if match:
            assignments[match.group(1)] = line
    return assignments


def _replace_atomically(destination: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as config_file:
            config_file.write(content)
            config_file.flush()
            os.fsync(config_file.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def merge_missing_config(
    template: Path = CONFIG_TEMPLATE, destination: Path = CONFIG_FILE
) -> tuple[str, ...]:
    """Append template assignments missing from an existing config without changing its values."""
    template_assignments = _assignment_lines(template.read_text(encoding="utf-8"))
    current = destination.read_bytes()
    existing_keys = set(_assignment_lines(current.decode("utf-8-sig")))
    missing_keys = tuple(key for key in template_assignments if key not in existing_keys)
    if not missing_keys:
        print(f"配置字段已是最新：{destination}")
        return ()

    newline = b"\r\n" if b"\r\n" in current else b"\n"
    separator = b"" if not current else newline if current.endswith((b"\n", b"\r")) else newline * 2
    added_lines = [
        "# ── 订阅更新自动补充的配置 ──────────────────────────────────────────",
        *(template_assignments[key] for key in missing_keys),
    ]
    addition = newline.join(line.encode("utf-8") for line in added_lines) + newline
    _replace_atomically(destination, current + separator + addition)
    print(f"已补充配置字段：{', '.join(missing_keys)}")
    return missing_keys


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
    old_umask = os.umask(0o077)
    try:
        # Always create the editable config before dependency installation can fail.
        created = ensure_config()
        if not created:
            merge_missing_config()
        code = install_project()
        if code:
            print("Python 依赖安装失败，请查看上方 pip 日志。", file=sys.stderr)
            return code
        print("CheckinTools 青龙初始化完成。")
        return 0
    except (OSError, UnicodeError) as exc:
        print(f"青龙初始化失败：{exc}", file=sys.stderr)
        return 2
    finally:
        os.umask(old_umask)


if __name__ == "__main__":
    raise SystemExit(main())
