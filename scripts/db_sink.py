#!/usr/bin/env python3
"""Hermes 入库 Hook 统一入口 — 按 hermes_tasks.task_type / 意图分发到 01/02/03/04。

相对 xa：保留 hook_connection_scope；不含 custom_05；无意图时默认 report_04，避免误伤写报。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_SCRIPTS = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if not os.environ.get("HERMES_HOME", "").strip():
    os.environ["HERMES_HOME"] = str(_REPO_ROOT)

from collect_01 import db
from collect_01.task_store import is_collect_intent
from expand_02.task_store import is_expand_intent
from report_04.task_store import is_report_intent
from verify_03.task_store import is_verify_intent


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


def _extra(payload: Dict[str, Any]) -> Dict[str, Any]:
    ex = payload.get("extra")
    return ex if isinstance(ex, dict) else {}


def _task_type_from_id(task_id: str) -> Optional[str]:
    if not task_id:
        return None
    row = db.fetch_one("SELECT task_type FROM hermes_tasks WHERE task_id=%s", (task_id,))
    if not row:
        return None
    return str(row.get("task_type") or "").strip() or None


def _task_type_from_session(session_id: str) -> Optional[str]:
    if not session_id:
        return None
    row = db.fetch_one(
        """
        SELECT task_type FROM hermes_tasks
        WHERE session_id=%s AND status IN ('pending', 'running')
        ORDER BY created_at DESC LIMIT 1
        """,
        (session_id,),
    )
    if not row:
        return None
    return str(row.get("task_type") or "").strip() or None


def _sink_for_task_type(ttype: Optional[str]):
    """按库内 task_type 选 sink；未知类型返回 None。"""
    if ttype == "account_collect":
        from collect_01 import sink as collect_sink

        return collect_sink
    if ttype == "account_expand":
        from expand_02 import sink as expand_sink

        return expand_sink
    if ttype == "account_verify":
        from verify_03 import sink as verify_sink

        return verify_sink
    if ttype == "account_report":
        from report_04 import sink as report_sink

        return report_sink
    return None


def _resolve_sink_module(payload: Dict[str, Any]):
    ex = _extra(payload)
    session_id = str(payload.get("session_id") or "").strip()

    for key in ("gateway_session_key", "session_key"):
        raw = str(ex.get(key) or "").strip()
        if raw.startswith("task:"):
            tid = raw[5:].strip()
            sink = _sink_for_task_type(_task_type_from_id(tid))
            if sink is not None:
                return sink
            break

    sink = _sink_for_task_type(_task_type_from_session(session_id))
    if sink is not None:
        return sink

    user_message = str(ex.get("user_message") or "").strip()
    # 意图优先级：写报 > 核查 > 扩建 > 采集（保护现有写报）
    if is_report_intent(user_message):
        from report_04 import sink as report_sink

        return report_sink
    if is_verify_intent(user_message):
        from verify_03 import sink as verify_sink

        return verify_sink
    if is_expand_intent(user_message):
        from expand_02 import sink as expand_sink

        return expand_sink
    if is_collect_intent(user_message):
        from collect_01 import sink as collect_sink

        return collect_sink

    # 无意图默认写报（相对 xa 默认 collect 的有意差异）
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
