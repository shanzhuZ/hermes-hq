# -*- coding: utf-8 -*-
"""04 写报 · 主进程 Stop 门闩。

防止主进程在管线未完成时因口头收束而 stop。
不改续跑逻辑；仅在 pre_verify 返回 continue 文案，由 Hermes 同会话再开一轮。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from report_04.gates import (
    get_step_status,
    identity_step_terminal,
    is_v3_report_tree,
    osint_web_status,
)

logger = logging.getLogger(__name__)

_TERMINAL = frozenset({"completed", "failed", "skipped"})

# 旧树：身份核验相关根步
_COLLISION_STEPS = (
    "step4_identity",
)

# collision=碰撞未齐；posts=发文未落地；web=v3 公开信息检索未开
_REASON_COLLISION = "collision"
_REASON_POSTS = "posts"
_REASON_WEB = "web_intel"
_REASON_IDENTITY = "identity"


def collision_phase_incomplete(task_id: str) -> bool:
    """旧树：四、身份关联核验是否尚未终态。"""
    for sk in _COLLISION_STEPS:
        st = get_step_status(task_id, sk)
        if st is None:
            continue
        if st not in _TERMINAL:
            return True
    return False


def _posts_still_due(task_id: str) -> bool:
    """发文门禁开且仍有待采 / 无帖 → 视为发文未落地。"""
    try:
        from report_04.gates import can_run_step7_collect, posts_substantively_ready

        if posts_substantively_ready(task_id):
            return False
        if not can_run_step7_collect(task_id):
            return False
        from report_04.session_continue import post_count
        from report_04.step_reconcile import list_unattempted_post_platforms

        todo = list_unattempted_post_platforms(task_id) or []
        if todo:
            return True
        return post_count(task_id) <= 0
    except Exception as exc:
        logger.warning("stop_gate 发文待采检查失败 task=%s: %s", task_id, exc)
        return False


def classify_stop_block(task_id: str) -> Optional[str]:
    """返回拦截原因；None 表示允许 stop。"""
    if not task_id:
        return None
    try:
        from report_04.session_continue import has_final_report

        if has_final_report(task_id):
            return None
    except Exception:
        if get_step_status(task_id, "step7_report") == "completed":
            return None

    # —— v3：主账号→Maigret→认定→网页备料→发文→报告 ——
    if is_v3_report_tree(task_id):
        s2 = get_step_status(task_id, "step2_maigret")
        if s2 is not None and s2 not in _TERMINAL:
            return _REASON_IDENTITY
        if not identity_step_terminal(task_id):
            return _REASON_IDENTITY
        s_web = osint_web_status(task_id)
        if s_web is None or s_web not in _TERMINAL:
            return _REASON_WEB
        s_posts = get_step_status(task_id, "step5_posts")
        if s_posts is None or s_posts not in _TERMINAL:
            if _posts_still_due(task_id) or s_posts in {"pending", "running", None}:
                return _REASON_POSTS
        s_report = get_step_status(task_id, "step7_report")
        if s_report is None or s_report not in _TERMINAL:
            return _REASON_POSTS
        return None

    # —— 旧树兼容 ——
    s4 = get_step_status(task_id, "step3_profiles")
    if s4 not in _TERMINAL:
        return None

    if collision_phase_incomplete(task_id):
        return _REASON_COLLISION

    if _posts_still_due(task_id):
        return _REASON_POSTS

    return None


def should_block_report_stop(task_id: str) -> bool:
    """管线未完成 → 禁止主进程 stop。"""
    return classify_stop_block(task_id) is not None


def _collision_status_line(task_id: str) -> str:
    parts = []
    for sk in _COLLISION_STEPS:
        parts.append(f"{sk}={get_step_status(task_id, sk) or 'pending'}")
    return "; ".join(parts)


def _posts_todo_hint(task_id: str) -> str:
    try:
        from report_04.step_reconcile import list_unattempted_post_platforms

        todo = list_unattempted_post_platforms(task_id) or []
        if not todo:
            return "请对全部已认定账号调用发文工具"
        hints = "; ".join(
            f"{x.get('platform')}:{x.get('tool_hint')}" for x in todo[:6]
        )
        return f"尚未尝试 {len(todo)} 个：{hints}"
    except Exception:
        return "请对全部已认定账号调用发文工具"


def build_stop_gate_message(
    task_id: str,
    *,
    attempt: int = 0,
    reason: Optional[str] = None,
) -> str:
    """合成 user 催促文案（注入主会话，禁止 stop）。"""
    n = int(attempt) + 1
    why = reason or classify_stop_block(task_id) or _REASON_COLLISION
    if why == _REASON_WEB:
        return (
            "【系统·禁止结束会话】账号认定已完成，步骤4公开信息检索尚未执行。"
            "禁止 stop，禁止只写「下面进入步骤4」。"
            "本回合必须立刻调用 web_search / web_extract 为八章备料（禁止再搜社交账号）。"
            f"（Stop门闩·网页备料第{n}次）"
        )
    if why == _REASON_IDENTITY:
        return (
            "【系统·禁止结束会话】Maigret/账号认定尚未收口。"
            "禁止 stop。若 Maigret 已完成请输出 [账号认定结论]；否则先完成步骤2。"
            f"（Stop门闩·认定第{n}次）"
        )
    if why == _REASON_POSTS:
        return (
            "【系统·禁止结束会话】发文/报告尚未完成。"
            "禁止 stop，禁止再复述「步骤完成」。"
            f"本回合必须继续：{_posts_todo_hint(task_id)}；发文齐后再写八章终稿。"
            f"（Stop门闩·发文第{n}次）"
        )
    status = _collision_status_line(task_id)
    return (
        "【系统·禁止结束会话】主页采集已收口，关联碰撞仍在由系统推进中"
        f"（{status}）。禁止 stop，禁止只复述「步骤4完成」。"
        "请保持会话：无工具可调时输出一句「碰撞进行中」即可；"
        "碰撞门禁一开必须立刻对 validated 调用发文工具，禁止结束会话。"
        f"（Stop门闩·碰撞第{n}次）"
    )


def try_advance_collision_before_nudge(store: Any, task_id: str) -> None:
    """门闩触发时顺带推一档碰撞，缩短真空（不涉及续跑）。"""
    if is_v3_report_tree(task_id):
        return
    try:
        from report_04.engine import advance_collision_phase

        advance_collision_phase(store, task_id, max_rounds=4)
    except Exception as exc:
        logger.warning("stop_gate 推进碰撞失败 task=%s: %s", task_id, exc)


def pre_verify_continue_message(
    store: Any,
    task_id: str,
    *,
    attempt: int = 0,
) -> Optional[str]:
    """供 sink pre_verify：需拦截则返回文案，否则 None。"""
    reason = classify_stop_block(task_id)
    if not reason:
        return None

    if reason == _REASON_COLLISION:
        try_advance_collision_before_nudge(store, task_id)
        reason = classify_stop_block(task_id)
        if not reason:
            logger.info("stop_gate 推进后已可放行 stop task=%s", task_id)
            return None

    msg = build_stop_gate_message(task_id, attempt=attempt, reason=reason)
    logger.warning(
        "stop_gate 拦截主进程 stop task=%s reason=%s attempt=%s",
        task_id,
        reason,
        attempt,
    )
    return msg
