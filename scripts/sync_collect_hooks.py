#!/usr/bin/env python3
"""将 01 采集 db_sink Hook 同步到仓库根目录 config.yaml（HERMES_HOME 指向本仓库时使用）。"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENTS = (
    "pre_llm_call",
    "pre_tool_call",
    "post_tool_call",
    "post_llm_call",
    "pre_verify",
    "on_session_end",
)


def _default_python() -> str:
    """跨平台默认解释器：优先 HERMES_PYTHON，否则当前进程。"""
    env_py = (os.environ.get("HERMES_PYTHON") or "").strip()
    if env_py:
        return env_py
    return sys.executable or ("python3" if os.name != "nt" else "python")


def _hook_command() -> str:
    # 写入可跨平台展开的占位符；运行时由 hermes load_config / shell_hooks expandvars
    return "${HERMES_PYTHON} ${HERMES_HOME}/scripts/db_sink.py"


def build_hooks_block() -> str:
    cmd = _hook_command()
    lines = ["hooks:"]
    for ev in EVENTS:
        lines.append(f"  {ev}:")
        lines.append(f"    - command: {cmd}")
        lines.append("      timeout: 120")
    lines.append("hooks_auto_accept: true")
    return "\n".join(lines) + "\n"


def patch_config(config_path: Path) -> None:
    text = config_path.read_text(encoding="utf-8")
    block = build_hooks_block()
    patterns = [
        re.compile(r"(?ms)^hooks:\r?\n.*?^(?=hooks_auto_accept:|personalities:|security:|known_plugin)"),
        re.compile(r"(?ms)^hooks_auto_accept:.*?\r?\nhooks:\r?\n.*?^(?=known_plugin|personalities:|security:)"),
    ]
    for pattern in patterns:
        if pattern.search(text):
            text = pattern.sub(block, text, count=1)
            config_path.write_text(text, encoding="utf-8")
            print(f"已更新 hooks -> {_hook_command()}")
            print(f"配置文件: {config_path}")
            return
    print(f"未在 {config_path} 中找到 hooks 块", file=sys.stderr)
    sys.exit(1)


def patch_allowlist(allowlist_path: Path) -> None:
    cmd = _hook_command()
    data: dict = {"approvals": []}
    if allowlist_path.is_file():
        try:
            data = json.loads(allowlist_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"approvals": []}
    approvals = [a for a in data.get("approvals", []) if a.get("command") != cmd]
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for ev in EVENTS:
        approvals.append(
            {
                "event": ev,
                "command": cmd,
                "approved_at": now,
                "script_mtime_at_approval": now,
            }
        )
    data["approvals"] = approvals
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"已更新 allowlist: {allowlist_path}")


def _warn_legacy_config() -> None:
    local = os.environ.get("LOCALAPPDATA", "").strip()
    repo_cfg = REPO_ROOT / "config.yaml"
    if local:
        legacy = Path(local) / "hermes" / "config.yaml"
        if legacy.is_file() and legacy.resolve() != repo_cfg.resolve():
            print(
                f"\n注意：仍存在旧版独立安装配置 {legacy}\n"
                f"  hermes chat / gateway 仅在设置 HERMES_HOME={REPO_ROOT} 时才会读仓库 config.yaml。\n"
                f"  Windows: .\\scripts\\hermes.ps1 chat\n"
                f"  Linux:   ./scripts/hermes.sh chat"
            )
            return
    home = os.environ.get("HOME", "").strip()
    if home:
        legacy = Path(home) / ".hermes" / "config.yaml"
        if legacy.is_file() and legacy.resolve() != repo_cfg.resolve():
            print(
                f"\n注意：仍存在 ~/.hermes/config.yaml\n"
                f"  请用 ./scripts/hermes.sh 启动，确保 HERMES_HOME={REPO_ROOT}。"
            )


def main() -> int:
    config_path = REPO_ROOT / "config.yaml"
    if not config_path.is_file():
        print(f"未找到仓库配置: {config_path}", file=sys.stderr)
        return 1
    patch_config(config_path)
    patch_allowlist(REPO_ROOT / "shell-hooks-allowlist.json")
    _warn_legacy_config()
    print("\n请重新打开 hermes chat（或重启 gateway）后再发起采集任务。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
