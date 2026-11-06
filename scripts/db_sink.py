#!/usr/bin/env python3
"""Hermes 入库 Hook 统一入口 — hermes-hq 仅保留 04 写报，统一分发到 report_04.sink。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

_SCRIPTS = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if not os.environ.get("HERMES_HOME", "").strip():
    os.environ["HERMES_HOME"] = str(_REPO_ROOT)


def _ensure_utf8_stdio() -> None:
    """Hook 子进程在 Windows 上默认 GBK，强制 UTF-8 避免 stderr 日志炸掉。"""
    import io

    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        elif hasattr(stream, "buffer"):
            wrapper = io.TextIOWrapper(
                stream.buffer,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )
            setattr(sys, name, wrapper)


def _resolve_sink_module(payload: Dict[str, Any]):
    # hermes-hq：只跑 04 写报
    from report_04 import sink as report_sink

    return report_sink


def main() -> int:
    _ensure_utf8_stdio()
    try:
        if hasattr(sys.stdin, "buffer"):
            data = sys.stdin.buffer.read()
        else:
            data = sys.stdin.read().encode("utf-8", errors="replace")
        if not data:
            return 0
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError:
            raw = data.decode("gbk", errors="replace")
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 0
        sink = _resolve_sink_module(payload)
        # 单次 Hook 复用 MySQL 连接，避免远程库每次建连把 120s 墙钟耗尽
        from collect_01.db import hook_connection_scope

        with hook_connection_scope():
            result = sink.handle_event(payload)
        # pre_tool_call / pre_llm_call / pre_verify 可向 Agent 回写 block / context / continue
        if isinstance(result, dict) and result:
            sys.stdout.write(json.dumps(result, ensure_ascii=False))
            sys.stdout.flush()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception("db_sink 异常: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
