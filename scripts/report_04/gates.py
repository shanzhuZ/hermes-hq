"""04 写报 — 步骤完成门禁。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional  # Any：store 标记在飞时使用

from collect_01 import db
from report_04.phases import ANALYSIS_STEP_KEYS, PROFILE_PARENT_STEP_KEY, TASK_TYPE


def get_step_status(task_id: str, step_key: str) -> Optional[str]:
    row = db.fetch_one(
        "SELECT status FROM collect_phase_steps WHERE task_id=%s AND step_key=%s",
        (task_id, step_key),
    )
    return str((row or {}).get("status") or "").strip() or None


def is_v3_report_tree(task_id: str) -> bool:
    """v3 树：有 step3_identity / step2_maigret，且通常无旧 step4_identity 专步。"""
    if get_step_status(task_id, "step3_identity") is not None:
        return True
    if get_step_status(task_id, "step2_maigret") is not None:
        return True
    return False


def osint_web_status(task_id: str) -> Optional[str]:
    """公开信息检索：新 step4_osint_web，旧 step2_osint_web。"""
    st = get_step_status(task_id, "step4_osint_web")
    if st is not None:
        return st
    return get_step_status(task_id, "step2_osint_web")


def get_step_payload(task_id: str, step_key: str) -> Dict[str, Any]:
    row = db.fetch_one(
        "SELECT payload_json FROM collect_phase_steps WHERE task_id=%s AND step_key=%s",
        (task_id, step_key),
    )
    try:
        payload = json.loads((row or {}).get("payload_json") or "{}")
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def is_post_tool_inflight(task_id: str, platform: str) -> bool:
    """该平台发文 MCP 是否仍在飞（pre_tool 已记、post_tool 未清）。"""
    from report_04.phases import post_platform_step_key

    plat = str(platform or "").strip().lower()
    if not plat:
        return False
    payload = get_step_payload(task_id, post_platform_step_key(plat))
    return bool(payload.get("post_tool_inflight"))


def list_inflight_post_platforms(task_id: str) -> List[str]:
    """返回仍标记 post_tool_inflight 的发文平台。"""
    from report_04.phases import POST_PARENT_STEP_KEY

    rows = db.fetch_all(
        """
        SELECT step_key, payload_json FROM collect_phase_steps
        WHERE task_id=%s AND parent_step_key=%s
          AND (step_key LIKE 'step5_post_%%' OR step_key LIKE 'step5_post_%%')
        """,
        (task_id, POST_PARENT_STEP_KEY),
    )
    out: List[str] = []
    for r in rows or []:
        sk = str(r.get("step_key") or "")
        try:
            payload = json.loads(r.get("payload_json") or "{}")
        except Exception:
            payload = {}
        if isinstance(payload, dict) and payload.get("post_tool_inflight"):
            plat = ""
            if sk.startswith("step5_post_"):
                plat = sk.replace("step5_post_", "", 1)
            elif sk.startswith("step5_post_"):
                plat = sk.replace("step5_post_", "", 1)
            if plat:
                out.append(plat)
    return out


def has_inflight_post_tools(task_id: str) -> bool:
    return bool(list_inflight_post_platforms(task_id))


def heal_stale_post_tool_inflight(
    store: Any,
    task_id: str,
    *,
    max_age_sec: float = 600.0,
) -> int:
    """超过墙钟仍标在飞：自清，避免永久挡关父壳（Twitter 工具超时约 420s）。"""
    import time
    from report_04.phases import POST_PARENT_STEP_KEY

    rows = db.fetch_all(
        """
        SELECT step_key, payload_json, updated_at FROM collect_phase_steps
        WHERE task_id=%s AND parent_step_key=%s AND step_key LIKE 'step5_post_%%'
        """,
        (task_id, POST_PARENT_STEP_KEY),
    )
    n = 0
    now = time.time()
    for r in rows or []:
        sk = str(r.get("step_key") or "")
        try:
            payload = json.loads(r.get("payload_json") or "{}")
        except Exception:
            payload = {}
        if not isinstance(payload, dict) or not payload.get("post_tool_inflight"):
            continue
        since = payload.get("inflight_since")
        age = None
        try:
            if since is not None:
                age = now - float(since)
        except Exception:
            age = None
        if age is None:
            # 无 since 时用 updated_at 兜底
            try:
                ua = r.get("updated_at")
                if ua is not None and hasattr(ua, "timestamp"):
                    age = now - float(ua.timestamp())
            except Exception:
                age = None
        if age is not None and age < float(max_age_sec):
            continue
        plat = sk.replace("step5_post_", "", 1) if sk.startswith("step5_post_") else ""
        if store is not None and plat:
            clear_post_tool_inflight(store, task_id, plat)
        else:
            payload["post_tool_inflight"] = False
            payload["inflight_tool"] = None
            payload["inflight_since"] = None
            db.execute(
                "UPDATE collect_phase_steps SET payload_json=%s WHERE task_id=%s AND step_key=%s",
                (db.json_dumps(payload), task_id, sk),
            )
        n += 1
    return n


def mark_post_tool_inflight(
    store: Any,
    task_id: str,
    platform: str,
    *,
    tool_name: str = "",
) -> None:
    """pre_tool：标记平台发文工具在飞，禁止 reconcile 提前 completed。

    成功路径须保持到 post_tool 完成 collect_posts 入库之后再 clear；
    禁止在工具刚返回、尚未 persist 时清除。
    """
    import time
    from report_04.phases import post_platform_step_key

    plat = str(platform or "").strip().lower()
    if not plat:
        return
    sk = post_platform_step_key(plat)
    store.ensure_step_row(task_id, sk)
    cur = get_step_status(task_id, sk) or "pending"
    # skipped 终态禁止回开；其余一律钉 running 直到 post_tool
    if cur == "skipped":
        store.set_step_status(
            task_id,
            sk,
            "skipped",
            payload={
                "post_tool_inflight": True,
                "inflight_tool": str(tool_name or "")[:120],
                "inflight_since": time.time(),
            },
        )
        return
    store.set_step_status(
        task_id,
        sk,
        "running",
        message=f"{plat} 发文工具执行中…",
        payload={
            "post_tool_inflight": True,
            "inflight_tool": str(tool_name or "")[:120],
            "inflight_since": time.time(),
        },
        force_reopen=(cur in {"completed", "failed"}),
    )


def clear_post_tool_inflight(store: Any, task_id: str, platform: str) -> None:
    """post_tool：清除在飞标记。"""
    from report_04.phases import post_platform_step_key

    plat = str(platform or "").strip().lower()
    if not plat:
        return
    sk = post_platform_step_key(plat)
    if not get_step_payload(task_id, sk).get("post_tool_inflight"):
        return
    cur = get_step_status(task_id, sk) or "pending"
    store.set_step_status(
        task_id,
        sk,
        cur,
        payload={
            "post_tool_inflight": False,
            "inflight_tool": None,
            "inflight_since": None,
        },
    )


def _seed_platform(task_id: str) -> str:
    row = db.fetch_one("SELECT seed_json FROM hermes_tasks WHERE task_id=%s", (task_id,))
    if not row:
        return "twitter"
    try:
        seed = json.loads(row.get("seed_json") or "{}")
    except json.JSONDecodeError:
        return "twitter"
    return str(seed.get("platform") or "twitter")


def count_image_streams(task_id: str) -> int:
    row = db.fetch_one(
        """
        SELECT COUNT(*) AS c FROM collect_identity_streams
        WHERE task_id=%s AND stream_type='image'
        """,
        (task_id,),
    )
    return int((row or {}).get("c") or 0)


def count_image_streams_processed(task_id: str) -> int:
    row = db.fetch_one(
        """
        SELECT COUNT(*) AS c FROM collect_identity_streams
        WHERE task_id=%s AND stream_type='image'
          AND validation_status IN ('processed', 'pass', 'fail')
        """,
        (task_id,),
    )
    return int((row or {}).get("c") or 0)


def is_stream_compare_ready(task_id: str) -> bool:
    n = count_image_streams(task_id)
    if n == 0:
        return True
    return count_image_streams_processed(task_id) >= n


def discovery_steps_terminal(task_id: str) -> bool:
    """Maigret（step2_maigret）终态后，才允许认定/候选主页收口。"""
    s2 = get_step_status(task_id, "step2_maigret")
    if s2 is None:
        # 兼容旧树曾把网页发现挂在 step2_osint_web
        s2 = get_step_status(task_id, "step2_osint_web")
    return s2 in {"completed", "skipped"}


def can_run_step2_maigret(task_id: str) -> bool:
    """主账号结束后即可 Maigret。"""
    return get_step_status(task_id, "step1_seed") in {"completed", "skipped", "running"}


def can_run_step2_osint_web(task_id: str) -> bool:
    """公开信息检索（step4_osint_web）：须账号认定完成。"""
    return identity_step_terminal(task_id)


def can_close_step4_parent(task_id: str) -> bool:
    return discovery_steps_terminal(task_id)


def can_update_step4_children(task_id: str) -> bool:
    """Maigret 结束后才允许创建/更新候选主页子节点（step3_profiles）。"""
    return discovery_steps_terminal(task_id)


def identity_step_terminal(task_id: str) -> bool:
    """账号认定终态（新 step3_identity / 旧 step4_identity）。"""
    for key in ("step3_identity", "step4_identity"):
        st = get_step_status(task_id, key)
        if st in {"completed", "skipped"}:
            return True
    return False


def can_update_step7_children(task_id: str) -> bool:
    """身份核验结束后才允许创建或更新发文子节点。"""
    return can_run_step7_collect(task_id)


def step7_collect_active(task_id: str) -> bool:
    """发文父壳已开始才允许创建或更新发文子步骤。"""
    st = get_step_status(task_id, "step5_posts")
    if st is None:
        st = get_step_status(task_id, "step5_posts")
    return st in {"running", "completed", "skipped"}


def can_advance_to_osint(task_id: str) -> Dict[str, Any]:
    """hq 已下线社工库专步；恒为可跳过。"""
    return {"ok": True, "message": "hq 无 step6_osint_es，跳过"}


def can_advance_to_pdl(task_id: str) -> Dict[str, Any]:
    """hq 已下线 PDL 专步；恒为可跳过。"""
    return {"ok": True, "message": "hq 无 step6_pdl，跳过"}


def osint_terminal_or_absent(task_id: str) -> bool:
    return True


def pdl_terminal_or_absent(task_id: str) -> bool:
    return True


def can_run_step7_collect(task_id: str) -> bool:
    """认定 + 公开信息检索完成后允许发文（v3：…→3认定→4网页备料→5发文）。"""
    if not identity_step_terminal(task_id):
        if get_step_status(task_id, "step6_validated") != "completed":
            return False
    s_web = get_step_status(task_id, "step4_osint_web")
    if s_web is None:
        s_web = get_step_status(task_id, "step2_osint_web")
    return s_web in {"completed", "skipped"}


def report_prerequisites_ready(task_id: str) -> bool:
    """点亮八章写报（step7_report）前的前置门禁。

    v3：账号认定 + 公开信息检索终态即可（无旧 step6_validated / 4.3 / 4.7）。
    旧树：仍要求 step6_validated completed，且社工库/PDL 终态或无行。
    """
    if is_v3_report_tree(task_id):
        if not identity_step_terminal(task_id):
            return False
        return osint_web_status(task_id) in {"completed", "skipped"}
    if get_step_status(task_id, "step6_validated") != "completed":
        return False
    if not osint_terminal_or_absent(task_id):
        return False
    if not pdl_terminal_or_absent(task_id):
        return False
    return True


def _step3_profile_children_pending(task_id: str) -> Optional[str]:
    """步骤四仍有 pending/running 子节点时返回其 step_key。"""
    rows = db.fetch_all(
        """
        SELECT step_key, status FROM collect_phase_steps
        WHERE task_id=%s AND parent_step_key=%s
        """,
        (task_id, PROFILE_PARENT_STEP_KEY),
    )
    for row in rows:
        st = str(row.get("status") or "")
        if st in {"pending", "running"}:
            return str(row.get("step_key") or "")
    return None


def step3_profiles_terminal(task_id: str) -> bool:
    """主页采集父节点与子节点均已结束（hq: step3_profiles）。"""
    parent = get_step_status(task_id, "step3_profiles")
    if parent is None:
        parent = get_step_status(task_id, "step3_profiles")
    if parent not in {"completed", "skipped"}:
        return False
    return _step3_profile_children_pending(task_id) is None


def step3_profile_collect_started(task_id: str) -> bool:
    """是否已真正开始主页采集（hq: step3_profiles）。"""
    parent = get_step_status(task_id, "step3_profiles")
    if parent is None:
        parent = get_step_status(task_id, "step3_profiles")
    if parent in {"running", "completed", "skipped"}:
        return True
    rows = db.fetch_all(
        """
        SELECT status FROM collect_phase_steps
        WHERE task_id=%s AND parent_step_key=%s
        """,
        (task_id, PROFILE_PARENT_STEP_KEY),
    )
    return any(str(r.get("status") or "") == "running" for r in rows)


def seconds_since_last_tool(
    task_id: str,
    *,
    tool_names: Optional[List[str]] = None,
    phase_prefix: Optional[str] = None,
) -> Optional[float]:
    """距最近一次匹配工具成功的秒数；无记录返回 None。"""
    from datetime import datetime

    clauses = ["task_id=%s", "status='success'"]
    params: List[Any] = [task_id]
    if tool_names:
        placeholders = ",".join(["%s"] * len(tool_names))
        clauses.append(f"tool_name IN ({placeholders})")
        params.extend(tool_names)
    if phase_prefix:
        clauses.append("phase LIKE %s")
        params.append(f"{phase_prefix}%")
    row = db.fetch_one(
        f"""
        SELECT MAX(executed_at) AS last_at FROM hermes_tool_outputs
        WHERE {' AND '.join(clauses)}
        """,
        tuple(params),
    )
    last_at = (row or {}).get("last_at")
    if last_at is None:
        return None
    if hasattr(last_at, "timestamp"):
        try:
            return max(0.0, (datetime.now() - last_at).total_seconds())
        except Exception:
            return None
    return None


def can_advance_to_step5(task_id: str) -> Dict[str, Any]:
    """Maigret 齐后可进账号认定（step3_identity）。"""
    s1 = get_step_status(task_id, "step1_seed")
    if s1 != "completed":
        return {"ok": False, "message": f"step1_seed={s1 or 'pending'}"}
    if not discovery_steps_terminal(task_id):
        return {"ok": False, "message": "step2_maigret 未终态"}
    return {"ok": True, "message": "满足账号认定推进条件"}


def can_advance_to_step7(task_id: str) -> Dict[str, Any]:
    """认定 + 公开信息检索完成后可进发文采集（step5_posts）。"""
    if not identity_step_terminal(task_id):
        return {"ok": False, "message": "step3_identity 未完成"}
    s3 = get_step_status(task_id, "step3_profiles")
    if s3 in {"pending", "running"}:
        pending_child = _step3_profile_children_pending(task_id)
        if pending_child or s3 == "running":
            return {"ok": False, "message": f"候选主页未收口（{pending_child or s3}）"}
    s_web = get_step_status(task_id, "step4_osint_web")
    if s_web is None:
        s_web = get_step_status(task_id, "step2_osint_web")
    if s_web not in {"completed", "skipped"}:
        return {"ok": False, "message": f"step4_osint_web={s_web or 'pending'}"}
    return {"ok": True, "message": "满足发文采集推进条件"}


def _platform_post_count(task_id: str, platform: str) -> int:
    row = db.fetch_one(
        "SELECT COUNT(*) AS c FROM collect_posts WHERE task_id=%s AND platform=%s",
        (task_id, platform),
    )
    return int((row or {}).get("c") or 0)


def posts_substantively_ready(task_id: str) -> bool:
    """发文实质已齐（只看发文子步/入库，不看视频）。

    用于关父壳、续跑 posts 等；进深度研判请用 can_advance_to_analysis
    （只认 step5_posts 父节点终态，父节点本身会等视频）。
    """
    if not can_advance_to_step7(task_id).get("ok"):
        return False
    try:
        from report_04.step_reconcile import list_unattempted_post_platforms

        if list_unattempted_post_platforms(task_id):
            return False
    except Exception:
        return False
    from report_04.phases import POST_PARENT_STEP_KEY

    rows = db.fetch_all(
        """
        SELECT step_key, status FROM collect_phase_steps
        WHERE task_id=%s AND parent_step_key=%s
        """,
        (task_id, POST_PARENT_STEP_KEY),
    )
    if rows:
        for r in rows:
            st = str(r.get("status") or "")
            if st in {"completed", "skipped"}:
                continue
            # running 但已有入库：视为实质完成（兼容旧「等视频」钉 running）
            if st == "running":
                sk = str(r.get("step_key") or "")
                plat = ""
                if sk.startswith("step5_post_"):
                    plat = sk.replace("step5_post_", "", 1)
                elif sk.startswith("step5_post_"):
                    plat = sk.replace("step5_post_", "", 1)
                if plat and _platform_post_count(task_id, plat) > 0:
                    continue
            return False
        return True
    # 无子节点：父已终态或已有发文
    s_posts = get_step_status(task_id, "step5_posts")
    if s_posts is None:
        s_posts = get_step_status(task_id, "step5_posts")
    if s_posts in {"completed", "skipped"}:
        return True
    row = db.fetch_one(
        "SELECT COUNT(*) AS c FROM collect_posts WHERE task_id=%s", (task_id,)
    )
    return int((row or {}).get("c") or 0) > 0


def can_advance_to_analysis(task_id: str) -> Dict[str, Any]:
    """发文齐后可进写报（方案 A 无专题中间步；函数名保留兼容）。

    父壳收口须等发文齐、视频终态、工具调用结束；禁止「帖已入库但 MCP 仍在飞」时进终稿。
    """
    gate = can_advance_to_step7(task_id)
    if not gate.get("ok"):
        return gate
    try:
        heal_stale_post_tool_inflight(None, task_id)
    except Exception:
        pass
    inflight = list_inflight_post_platforms(task_id)
    if inflight:
        return {
            "ok": False,
            "message": (
                f"发文工具仍在飞 platforms={','.join(inflight[:8])}，"
                "须等工具返回后再写八章终稿"
            ),
        }
    s7 = get_step_status(task_id, "step5_posts")
    if s7 is None:
        s7 = get_step_status(task_id, "step5_posts")
    if s7 in {"completed", "skipped"}:
        return {"ok": True, "message": "step5_posts 已终态且无在飞发文工具，可写八章终稿"}
    return {
        "ok": False,
        "message": f"step5_posts={s7 or 'pending'}（须发文父壳终态后再写八章终稿）",
    }


def analysis_steps_terminal(task_id: str) -> bool:
    for k in ANALYSIS_STEP_KEYS:
        if get_step_status(task_id, k) not in {"completed", "skipped"}:
            return False
    return True


# 发文齐后等 step8 系统管线的最长 hold 秒数；超时仍放行 write，避免永久卡住
_STEP8_WRITE_WAIT_SEC = 300


def step8_write_wait_sec() -> int:
    return int(_STEP8_WRITE_WAIT_SEC)


def _step8_wait_elapsed_sec(task_id: str) -> Optional[float]:
    """step8 进入 pending/running 后已等待秒数（优先 payload.wait_started_at）。"""
    import time
    from datetime import datetime

    row = db.fetch_one(
        """
        SELECT status, updated_at, started_at, payload_json
        FROM collect_phase_steps
        WHERE task_id=%s AND step_key=%s
        """,
        (task_id, "step6_basic"),
    )
    if not row:
        return None
    payload = {}
    try:
        payload = json.loads(row.get("payload_json") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    started = None
    raw_ws = payload.get("wait_started_at")
    if raw_ws:
        try:
            started = datetime.fromisoformat(str(raw_ws).replace("Z", ""))
        except Exception:
            started = None
    if started is None:
        started = row.get("started_at") or row.get("updated_at")
    if started is None:
        return 0.0
    if isinstance(started, datetime):
        return max(0.0, time.time() - started.timestamp())
    return 0.0


def step8_blocks_write(task_id: str) -> bool:
    """hq：不再用图片流专步挡终稿；专题研判由 analysis_steps_terminal 约束。"""
    return False


def format_step8_wait_hint(task_id: str) -> str:
    return ""


def can_complete_step11(task_id: str) -> Dict[str, Any]:
    if not analysis_steps_terminal(task_id):
        return {"ok": False, "message": "旧专题研判步尚未全部完成或跳过"}
    try:
        from report_04.video_report import can_write_report_after_videos

        wr = can_write_report_after_videos(task_id)
        if not wr.get("ok"):
            return {
                "ok": False,
                "message": wr.get("message") or "发文或视频未终态，不能写报",
            }
    except Exception as exc:
        return {"ok": False, "message": f"写报门禁检查失败:{exc}"}
    return {"ok": True, "message": "可完成公开资料核查报告"}
