"""04 写报编排：推断当前步骤、工具白名单、进入分析阶段收口 step7。"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, FrozenSet, Optional

from collect_01 import db
from report_04.gates import get_step_status
from report_04.osint_es import is_osint_es_tool
from report_04.pdl_enrich import is_pdl_tool
from report_04.phases import (
    ANALYSIS_STEP_KEYS,
    APIFY_POST_TOOLS,
    IDENTITY_STEP_KEY,
    INTAKE_STEP_KEY,
    MAIGRET_STEP_KEY,
    MAIGRET_TOOLS,
    OSINT_ES_STEP_KEY,
    OSINT_WEB_STEP_KEY,
    PDL_STEP_KEY,
    PHASE_ANALYSIS,
    PHASE_ANALYSIS_SHELL,
    PHASE_CONTENT,
    PHASE_REPORT_SHELL,
    POST_PARENT_STEP_KEY,
    POST_TOOLS,
    PROFILE_PARENT_STEP_KEY,
    PROFILE_TOOLS,
    STEP5_STREAM_TOOLS,
    TOOL_PLATFORM,
    WEB_SEARCH_TOOLS,
    root_step_keys,
)

logger = logging.getLogger(__name__)

# 防止 close_collect_parent_if_ready 回调用本函数形成递归
_ADVANCE_GUARD = set()
_ADVANCE_LOCK = threading.Lock()

# 各根步骤允许的工具（不含全局跳过的 clarify 等）
_STEP_WHITELIST: Dict[str, FrozenSet[str]] = {
    # step0 只允许网页检索补链接；禁止 Maigret（避免 C 判定前后仍扫账号、污染步骤树）
    INTAKE_STEP_KEY: WEB_SEARCH_TOOLS,
    "step1_seed": frozenset(
        {
            "mcp_twitter_get_user_info",
            "mcp_youtube_get_channel_stats",
            "mcp_weibo_get_profile",
            "mcp_bilibili_get_user_info",
            "mcp_apify_get_actor_run",
            "mcp_apify_get_dataset_items",
            *{
                t
                for t in (
                    "mcp_apify_apify__instagram_scraper",
                    "mcp_apify_clockworks__tiktok_scraper",
                    "mcp_apify_vujeen__telegram_channel_scraper",
                    "mcp_apify_headlessagent__facebook_profile_post_scraper",
                    "mcp_apify_knotless_cadence__github_profile_scraper",
                    "mcp_apify_harvestapi__linkedin_profile_scraper",
                )
            },
        }
    ),
    MAIGRET_STEP_KEY: MAIGRET_TOOLS,
    # v3 步骤3：输出认定结论 + 可采候选主页佐证（与 Skill 一致）；勿留空白名单拦死 TG/LI 等 Apify
    IDENTITY_STEP_KEY: PROFILE_TOOLS
    | frozenset({"mcp_apify_get_actor_run", "mcp_apify_get_dataset_items"}),
    "step4_identity": PROFILE_TOOLS
    | frozenset({"mcp_apify_get_actor_run", "mcp_apify_get_dataset_items"}),
    PROFILE_PARENT_STEP_KEY: PROFILE_TOOLS
    | frozenset({"mcp_apify_get_actor_run", "mcp_apify_get_dataset_items"}),
    OSINT_WEB_STEP_KEY: WEB_SEARCH_TOOLS,
    "step2_osint_web": WEB_SEARCH_TOOLS,  # 旧键兼容
    "step6_validated": frozenset(),
    "step6_osint_es": frozenset(
        {
            "mcp_es_search_search_country_wise",
            "mcp_es-search_search_country_wise",
            "mcp_es_search_list_es_indices",
            "mcp_es_search_es_cluster_health",
            "mcp_es-search_list_es_indices",
            "mcp_es-search_es_cluster_health",
        }
    ),
    "step6_pdl": frozenset({"mcp_pdl_person_search_person"}),
    "step6_geo_verify": frozenset(),
    "step6_relation_graph": frozenset(),
    "step6_rumor_sx": frozenset(),
    "step5_posts": POST_TOOLS
    | APIFY_POST_TOOLS
    | frozenset({"mcp_apify_get_actor_run", "mcp_apify_get_dataset_items"}),
    "step7_report": frozenset(),
}

# 仅业务执行 key（不含 step_plan / 七大阶段壳）；壳长期 pending 不可参与门禁推断
_ROOT_ORDER = tuple(root_step_keys())


def infer_gate_step(task_id: str) -> str:
    """推断当前应处根的步骤（用于白名单）。

    v3.1：0输入分析→1主账号→2 Maigret→3认定→4公开信息检索→5发文→6八章终稿。
    """
    # 输入分析未完成：强制停在 step0
    try:
        from report_04.intake import intake_open

        if intake_open(task_id):
            return INTAKE_STEP_KEY
    except Exception:
        pass

    # 仍有 validated 未调发文工具：强制停留发文（即使父节点被误标 completed）
    try:
        from report_04.gates import can_run_step7_collect
        from report_04.intake import is_person_path
        from report_04.step_reconcile import list_unattempted_post_platforms

        # C 路径发文已 skip，勿卡在 step5
        if not is_person_path(task_id):
            if can_run_step7_collect(task_id) and list_unattempted_post_platforms(task_id):
                return "step5_posts"
    except Exception:
        pass

    # 发文父壳 completed 且可写报 → 进终稿；skipped（C 路径）不得卡死在 step5
    try:
        from report_04.gates import can_advance_to_analysis

        analysis_ok = bool(can_advance_to_analysis(task_id).get("ok"))
    except Exception:
        analysis_ok = False
    s7 = get_step_status(task_id, "step5_posts")
    if analysis_ok:
        for key in ANALYSIS_STEP_KEYS:
            st = get_step_status(task_id, key)
            if st in {"pending", "running"}:
                return key
        report_ok = False
        try:
            from report_04.video_report import can_write_report_after_videos

            report_ok = bool(can_write_report_after_videos(task_id).get("ok"))
        except Exception:
            report_ok = False
        if not report_ok:
            # 等视频/发文齐：停在发文，勿进空白名单的 step7_report（否则模型只能空撞工具）
            if ANALYSIS_STEP_KEYS:
                return ANALYSIS_STEP_KEYS[-1]
            return "step5_posts"
        s11 = get_step_status(task_id, "step7_report")
        if s11 not in {"completed", "skipped"}:
            return "step7_report"
        return "step7_report"
    if s7 == "completed":
        # 发文已齐但仍不能写报（常见：等视频）→ 停在发文
        return "step5_posts"
    # s7 == skipped：人物无账号路径，继续向下推断 step3/step4

    # v3：认定结论已出后——候选主页未齐则仍停 profiles（放行 Apify）；齐了再进网页备料
    try:
        from report_04.gates import (
            discovery_steps_terminal,
            identity_step_terminal,
            is_v3_report_tree,
            osint_web_status,
            step3_profiles_terminal,
        )

        if is_v3_report_tree(task_id):
            # 必须先尊重步骤1/2；认定兜底只处理「前置均终态但 3.1 被误跳过」。
            if get_step_status(task_id, "step1_seed") not in {"completed", "skipped"}:
                return "step1_seed"
            if not discovery_steps_terminal(task_id):
                return MAIGRET_STEP_KEY
            # skipped/failed 不能冒充认定完成；活动任务必须回到 3.1 等真实结论。
            if not identity_step_terminal(task_id):
                return IDENTITY_STEP_KEY
            if not step3_profiles_terminal(task_id):
                return PROFILE_PARENT_STEP_KEY
            s_web = osint_web_status(task_id)
            if s_web is None or s_web in {"pending", "running"}:
                return OSINT_WEB_STEP_KEY
            s_posts = get_step_status(task_id, "step5_posts")
            if s_posts is None or s_posts in {"pending", "running"}:
                return "step5_posts"
            return "step7_report"
    except Exception:
        pass

    for key in _ROOT_ORDER:
        st = get_step_status(task_id, key)
        if st in {"pending", "running"}:
            return key
    return "step7_report"


def _allow_late_step5_post_collect(task_id: str, tool_name: str, phase: Optional[str]) -> bool:
    """步骤7 父节点已 completed 后允许补采发文（只入库，编排层禁止回开父节点）。

    写报门禁已开且 step7_report 已 running 时不再放行：避免「边写报边补采」空转。
    """
    from report_04.gates import report_prerequisites_ready

    if not report_prerequisites_ready(task_id):
        return False
    if get_step_status(task_id, "step5_posts") not in {"completed", "skipped"}:
        return False
    try:
        from report_04.video_report import can_write_report_after_videos

        if (
            get_step_status(task_id, "step7_report") == "running"
            and can_write_report_after_videos(task_id).get("ok")
        ):
            return False
    except Exception:
        pass
    ph = str(phase or "")
    if tool_name in POST_TOOLS:
        return True
    if tool_name in APIFY_POST_TOOLS or tool_name == "mcp_apify_get_actor_run":
        return True
    if tool_name == "mcp_apify_get_dataset_items" and ph.startswith("step5_post_"):
        return True
    return False


def block_tool_reason(
    task_id: str,
    tool_name: str,
    *,
    phase: Optional[str] = None,
) -> Optional[str]:
    """当前步骤不允许该工具时返回拦截原因。"""
    if not tool_name:
        return None
    # [COLLISION_DEMO_FAKE] 禁止 Agent 以假节点为 phase/gate 调工具 — 正式版删除本段
    try:
        from report_04.collision_demo_steps import block_agent_tool_for_demo_step

        demo_block = block_agent_tool_for_demo_step(phase, None)
        if demo_block:
            return demo_block
    except Exception:
        pass
    # [COLLISION_DEMO_FAKE] end
    if _allow_late_step5_post_collect(task_id, tool_name, phase):
        return None

    # 写报采集全程禁止 terminal：必须走 MCP/Apify，禁止 curl/shell 旁路
    if tool_name == "terminal":
        gate = infer_gate_step(task_id)
        tip = {
            "step0_intake": "请用 web_search/web_extract；找到链接后输出 [输入分析结论]。",
            "step1_seed": (
                "请调用主页 MCP/Apify："
                "LinkedIn→mcp_apify_harvestapi__linkedin_profile_scraper→"
                "get_actor_run→get_dataset_items。"
            ),
            "step2_maigret": "请调用 mcp_maigret_collect_accounts。",
            "step3_identity": "请输出认定结论；候选主页用 MCP/Apify，禁止 shell。",
            "step4_osint_web": "请用 web_search/web_extract/browser_*。",
            "step5_posts": "请调用发文类 MCP/Apify 工具。",
            "step7_report": "请直接在对话输出八章终稿，禁止 shell。",
        }.get(gate, "请按当前步骤白名单调用 MCP/Apify，禁止 terminal/curl。")
        return f"写报编排禁止调用 terminal（当前 {gate}）。{tip}"

    # 写报门禁已开：硬禁一切工具，逼模型直接出八章正文（禁止 write_file 旁路）
    # 拦截回包必须附材料包：否则模型会连撞工具空转十几分钟（见 494a step7≈807s）
    gate_early = infer_gate_step(task_id)
    if gate_early == "step7_report":
        try:
            from report_04.video_report import can_write_report_after_videos

            if can_write_report_after_videos(task_id).get("ok"):
                msg = (
                    f"当前已进入写报（step7_report），禁止调用 {tool_name}。"
                    "请立刻在对话中一次输出八章公开资料核查报告"
                    "（以「# {姓名} 公开资料核查报告」或「一、基本情况」起笔）。"
                    "禁止 write_file / web_search / web_extract / 发文 / 主页采集；"
                    "下一回合只许输出报告正文，禁止再调任何工具；缺项写「未核实」。"
                )
                try:
                    from report_04.engine import build_report_materials_pack

                    pack = build_report_materials_pack(task_id, max_chars=2800)
                    if pack:
                        msg = msg + "\n\n" + pack
                except Exception:
                    pass
                return msg
        except Exception:
            pass

    # Maigret：仅步骤2；step0 / 认定后 / 已 skip 一律禁止
    if tool_name.startswith("mcp_maigret_"):
        try:
            from report_04.intake import intake_open, is_person_path
            from report_04.gates import identity_step_terminal

            if intake_open(task_id):
                return (
                    "步骤0输入分析禁止调用 Maigret。"
                    "请用 web_search 查找社交主页链接；找到则 outcome=B 回填后进入步骤1/2。"
                )
            if is_person_path(task_id):
                return (
                    "当前为人物网页报告路径（无社交种子），禁止调用 Maigret。"
                    "请输出 [人物锚定结论] 后进入步骤4 web_search 备料。"
                )
            if identity_step_terminal(task_id):
                return (
                    "账号认定已完成，禁止再调用 Maigret。"
                    "请进入步骤4公开信息检索（web_search）或后续发文。"
                )
            s_id = get_step_status(task_id, IDENTITY_STEP_KEY) or get_step_status(
                task_id, "step4_identity"
            )
            if s_id in {"running", "completed", "skipped"}:
                return (
                    "已进入账号认定，禁止再调用 Maigret。"
                    "请输出 [账号认定结论] 或采候选主页佐证；禁止回流扫描。"
                )
            s_web = get_step_status(task_id, OSINT_WEB_STEP_KEY) or get_step_status(
                task_id, "step2_osint_web"
            )
            if s_web in {"running", "completed", "skipped"}:
                return "已进入公开信息检索，禁止再调用 Maigret。"
            s2 = get_step_status(task_id, MAIGRET_STEP_KEY)
            if s2 in {"completed", "skipped"}:
                return (
                    "Maigret 步骤已终态，禁止再调用。"
                    "请输出 [账号认定结论]；必要时采候选主页佐证。"
                )
        except Exception:
            pass

    gate = infer_gate_step(task_id)
    # [COLLISION_DEMO_FAKE]
    try:
        from report_04.collision_demo_steps import block_agent_tool_for_demo_step

        demo_block = block_agent_tool_for_demo_step(None, gate)
        if demo_block:
            return demo_block
    except Exception:
        pass
    # [COLLISION_DEMO_FAKE] end
    allowed = _STEP_WHITELIST.get(gate, frozenset())

    # 步骤3候选主页只采 Maigret 新发现的账号；种子主页已在步骤1入库，禁止重复扣费采集。
    if gate in {IDENTITY_STEP_KEY, "step4_identity", PROFILE_PARENT_STEP_KEY}:
        platform = str(TOOL_PLATFORM.get(tool_name) or "").strip().lower()
        if platform and tool_name in PROFILE_TOOLS:
            try:
                task = db.fetch_one(
                    "SELECT seed_json FROM hermes_tasks WHERE task_id=%s",
                    (task_id,),
                )
                seed = json.loads((task or {}).get("seed_json") or "{}")
                seed_platform = str(seed.get("platform") or "").strip().lower()
                row = db.fetch_one(
                    """
                    SELECT COUNT(*) AS c FROM collect_profiles
                    WHERE task_id=%s AND platform=%s
                    """,
                    (task_id, platform),
                )
                if (
                    platform == seed_platform
                    and get_step_status(task_id, "step1_seed") == "completed"
                    and int((row or {}).get("c") or 0) > 0
                ):
                    return (
                        f"{platform} 种子主页已在步骤1采集入库，禁止在步骤3重复调用 {tool_name}。"
                        "请仅采 Maigret 新候选；若无候选，直接输出 [账号认定结论]。"
                    )
                child_key = f"step3_profile_{platform}"
                child_status = get_step_status(task_id, child_key)
                if child_status is None:
                    return (
                        f"Maigret 未产生 {platform} 可采候选，禁止调用 {tool_name}。"
                        "请处理已有候选；若没有候选，输出 [账号认定结论]。"
                    )
                if child_status in {"completed", "skipped", "failed"}:
                    return (
                        f"{child_key} 已终态({child_status})，禁止重复调用 {tool_name}。"
                        "请继续其它候选或输出 [账号认定结论]。"
                    )
            except Exception as exc:
                logger.warning("种子主页重复采集检查失败 task=%s: %s", task_id, exc)

    # 社工库工具：仅 4.3；名称可能含 sanitize 后的 es_search
    if is_osint_es_tool(tool_name):
        if gate == OSINT_ES_STEP_KEY:
            return None
        return (
            f"当前编排步骤为 {gate}，禁止调用社工库工具 {tool_name}。"
            "须等 4.1+4.2 完成后进入 4.3（step6_osint_es），"
            "仅对 validated 账号的 profile_url 调用 search_country_wise。"
        )

    # PDL：4.2 后即可；与 4.3 并行（gate 在社工库时也放行）
    if is_pdl_tool(tool_name):
        if gate == PDL_STEP_KEY:
            return None
        if gate == OSINT_ES_STEP_KEY:
            try:
                from report_04.pdl_enrich import can_advance_to_pdl

                if can_advance_to_pdl(task_id).get("ok"):
                    return None
            except Exception:
                pass
        return (
            f"当前编排步骤为 {gate}，禁止调用 PDL 工具 {tool_name}。"
            "须等 4.1+4.2 完成后进入 4.7（step6_pdl），与社工库并行、不依赖 4.3 成败。"
        )

    # Apify dataset/run：phase 与 gate 不一致时按 phase 放宽（Hook 已写 phase）
    ph = str(phase or "")
    if tool_name in {"mcp_apify_get_dataset_items", "mcp_apify_get_actor_run"}:
        if ph.startswith("step3_profile_") and gate in {
            "step3_profiles",
            IDENTITY_STEP_KEY,
            "step4_identity",
            "step1_seed",
        }:
            return None
        if ph.startswith("step5_post_") and gate in {
            "step5_posts",
            "step6_validated",
            OSINT_ES_STEP_KEY,
            PDL_STEP_KEY,
        }:
            return None

    # 公开信息检索：墙钟/次数耗尽后禁止继续 web_*（须在 allowed 放行前拦截）
    if gate in {OSINT_WEB_STEP_KEY, "step2_osint_web"} and tool_name in WEB_SEARCH_TOOLS:
        try:
            from report_04.sink import step3_web_budget_exhausted

            budget = step3_web_budget_exhausted(task_id)
            if budget and budget != "already_done":
                return (
                    f"步骤4公开信息检索已达限制（{budget}）。"
                    "请立即停止 web_search/browser，进入步骤5发文采集。"
                )
        except Exception:
            pass

    if tool_name in allowed:
        return None

    return (
        f"当前编排步骤为 {gate}，禁止调用 {tool_name}。"
        f"请按写报顺序执行；若步骤7已收口，仅允许补采发文类工具。"
    )


def should_advance_on_tool(task_id: str, tool_name: str) -> bool:
    """步骤7未收口时，Agent 又调主页/检索类采集工具 → 视为进入分析前收口 step7。"""
    from report_04.gates import report_prerequisites_ready

    if not tool_name or not report_prerequisites_ready(task_id):
        return False
    if get_step_status(task_id, "step5_posts") in {"completed", "skipped"}:
        return False
    if tool_name in POST_TOOLS | APIFY_POST_TOOLS:
        return False
    if tool_name in {"mcp_apify_get_actor_run", "mcp_apify_get_dataset_items"}:
        return False
    if is_osint_es_tool(tool_name):
        return False
    if is_pdl_tool(tool_name):
        return False
    if tool_name in WEB_SEARCH_TOOLS | PROFILE_TOOLS:
        return True
    return False


def advance_to_analysis_phase(
    store: Any,
    task_id: str,
    reason: str,
    *,
    force_skip_unattempted: bool = False,
) -> bool:
    """
    进入写报：对「已尝试但 0 条」的发文子步 skip，收口父节点，点亮八章写报（v3 无 8/9/10）。
    默认禁止空 skip 未尝试发文的平台（逼 Agent 先调工具）；
    仅终稿/会话结束等路径可 force_skip_unattempted=True。
    """
    with _ADVANCE_LOCK:
        if task_id in _ADVANCE_GUARD:
            return False
        _ADVANCE_GUARD.add(task_id)
    try:
        return _advance_to_analysis_phase_body(
            store, task_id, reason, force_skip_unattempted=force_skip_unattempted
        )
    finally:
        with _ADVANCE_LOCK:
            _ADVANCE_GUARD.discard(task_id)


def _advance_to_analysis_phase_body(
    store: Any,
    task_id: str,
    reason: str,
    *,
    force_skip_unattempted: bool = False,
) -> bool:
    from report_04.step_reconcile import (
        _post_actor_without_dataset,
        _post_collect_attempted,
        close_collect_parent_if_ready,
        list_unattempted_post_platforms,
    )

    from report_04.gates import report_prerequisites_ready

    # v3 无 step6_validated；旧逻辑卡在此处会导致 step7_report 永久 pending
    if not report_prerequisites_ready(task_id):
        logger.info(
            "暂缓点亮写报：前置未齐（v3=认定+网页备料；旧树=validated） task=%s reason=%s",
            task_id,
            reason[:80],
        )
        return False

    leftover = list_unattempted_post_platforms(task_id)
    if leftover and not force_skip_unattempted:
        plats = [str(x.get("platform") or "") for x in leftover]
        logger.warning(
            "拒绝 advance_to_analysis：未尝试发文平台 task=%s platforms=%s reason=%s",
            task_id,
            ",".join(plats[:12]),
            reason[:80],
        )
        return False

    changed = False
    rows = db.fetch_all(
        """
        SELECT step_key, status FROM collect_phase_steps
        WHERE task_id=%s AND parent_step_key=%s
        """,
        (task_id, POST_PARENT_STEP_KEY),
    )
    for row in rows:
        step_key = str(row.get("step_key") or "")
        st = str(row.get("status") or "")
        if st not in {"pending", "running"}:
            continue
        plat = (
            step_key.replace("step5_post_", "", 1)
            if step_key.startswith("step5_post_")
            else ""
        )
        attempted = bool(plat) and (
            _post_collect_attempted(task_id, plat)
            or _post_actor_without_dataset(task_id, plat)
        )
        if not attempted and not force_skip_unattempted:
            # 保持 pending/running，禁止「进分析」空 skip
            continue
        msg = f"进入分析阶段收口：{reason[:120]}"
        if not attempted and force_skip_unattempted:
            msg = f"违规空过·未尝试发文后强制收口：{reason[:100]}"
        store.set_step_status(task_id, step_key, "skipped", message=msg)
        changed = True

    if close_collect_parent_if_ready(store, task_id, POST_PARENT_STEP_KEY, "发文采集已尝试完毕"):
        changed = True

    # 只认父壳终态再点亮研判（父壳收口已等发文+视频）
    if get_step_status(task_id, "step5_posts") not in {"completed", "skipped"}:
        logger.info(
            "暂缓点亮研判：step5_posts 未终态 task=%s reason=%s",
            task_id,
            reason[:80],
        )
        return changed

    # 方案 A：无专题子步则直进写报 phase；旧 ANALYSIS_STEP_KEYS 非空时仍点亮
    for step_key in ANALYSIS_STEP_KEYS:
        if get_step_status(task_id, step_key) == "pending":
            store.set_step_status(task_id, step_key, "running", message="分析进行中…")
            changed = True
    try:
        if ANALYSIS_STEP_KEYS:
            store.set_task_phase(task_id, PHASE_ANALYSIS)
        else:
            from report_04.phases import PHASE_REPORT

            store.set_task_phase(task_id, PHASE_REPORT)
            write_ok = False
            try:
                from report_04.video_report import can_write_report_after_videos

                write_ok = bool(can_write_report_after_videos(task_id).get("ok"))
            except Exception:
                write_ok = False
            if write_ok and get_step_status(task_id, "step7_report") == "pending":
                store.set_step_status(
                    task_id, "step7_report", "running", message="撰写八章核查报告…"
                )
                changed = True
            elif not write_ok:
                logger.info(
                    "暂缓点亮 step7_report：发文/视频未齐 task=%s reason=%s",
                    task_id,
                    reason[:80],
                )
    except Exception as exc:
        logger.warning("set_task_phase report/analysis 失败 task=%s: %s", task_id, exc)
    try:
        from report_04.image_assets import spawn_second_image_pipeline

        spawn_second_image_pipeline(task_id, store=store)
    except Exception as exc:
        logger.warning("advance_to_analysis 后台第二次图片管线失败 task=%s: %s", task_id, exc)
    if changed:
        logger.info("advance_to_analysis_phase task=%s reason=%s", task_id, reason[:80])
    return changed


def on_post_tool_step7_close_parent(store: Any, task_id: str) -> None:
    """子步终态后立刻关闭 step7 父节点（毫秒级，post_tool 末尾调用）。"""
    from report_04.step_reconcile import (
        close_collect_parent_if_ready,
        ensure_step7_parent_active,
        force_close_step5_posts_if_ready,
        reconcile_step7_from_post_tools,
    )

    try:
        reconcile_step7_from_post_tools(store, task_id)
    except Exception as exc:
        logger.warning("step7 回放发文工具失败 task=%s: %s", task_id, exc)
    try:
        ensure_step7_parent_active(store, task_id)
    except Exception as exc:
        logger.warning("step7 parent_active 失败 task=%s: %s", task_id, exc)
    close_collect_parent_if_ready(store, task_id, POST_PARENT_STEP_KEY, "发文采集已尝试完毕")
    # 双保险：子步已齐且无 leftover 时强制关父壳，避免 Hook 超时导致长期 running
    force_close_step5_posts_if_ready(store, task_id)


def close_open_steps_for_session_end(
    store: Any,
    task_id: str,
    *,
    reason: str = "会话结束：Agent stream 已结束",
) -> int:
    """stream/session 结束时：未终态步骤尽量收口，禁止流程空转。

    仅视频未终态时：不 skip 视频孙节点 / step11 / 发文父壳。发文 MCP 失败子步仍可 skip。
    """
    from report_04.step_reconcile import (
        close_collect_parent_if_ready,
        skip_exhausted_step5_post_mcp,
    )
    from report_04.task_store import _reconcile_report_post_child_steps

    updated = 0
    try:
        skip_exhausted_step5_post_mcp(store, task_id, session_end=True)
    except Exception as exc:
        logger.warning("session_end skip MCP 发文失败 task=%s: %s", task_id, exc)
    _reconcile_report_post_child_steps(store, task_id)
    store.reconcile_collect_child_steps(task_id)
    close_collect_parent_if_ready(store, task_id, POST_PARENT_STEP_KEY, "发文采集已尝试完毕")

    rows = db.fetch_all(
        """
        SELECT step_key, status, parent_step_key FROM collect_phase_steps
        WHERE task_id=%s AND status IN ('pending', 'running')
        ORDER BY step_order ASC, id ASC
        """,
        (task_id,),
    )
    msg = reason[:200]
    wait_videos = False
    try:
        from report_04.video_report import video_steps_terminal

        wait_videos = not bool(video_steps_terminal(task_id).get("ok"))
    except Exception:
        wait_videos = False
    for row in rows:
        step_key = str(row.get("step_key") or "")
        if not step_key:
            continue
        # 只等视频时：禁止把视频孙节点和写报步 skip 掉
        if wait_videos and (
            step_key.startswith("step5_video_")
            or step_key in {"step7_report", PHASE_REPORT_SHELL, POST_PARENT_STEP_KEY, PHASE_CONTENT}
        ):
            continue
        store.set_step_status(task_id, step_key, "skipped", message=msg)
        updated += 1

    # 再关一次父节点 / 阶段壳
    for parent in (
        PROFILE_PARENT_STEP_KEY,
        POST_PARENT_STEP_KEY,
        "step4_identity",
        PHASE_CONTENT,
        PHASE_ANALYSIS_SHELL,
        PHASE_REPORT_SHELL,
    ):
        try:
            if wait_videos and parent in {POST_PARENT_STEP_KEY, PHASE_CONTENT, PHASE_REPORT_SHELL}:
                continue
            if get_step_status(task_id, parent) in {"pending", "running"}:
                store.set_step_status(task_id, parent, "skipped", message=msg)
                updated += 1
        except Exception:
            pass
    close_collect_parent_if_ready(store, task_id, POST_PARENT_STEP_KEY, "发文采集已尝试完毕")
    close_collect_parent_if_ready(store, task_id, PROFILE_PARENT_STEP_KEY, "候选主页采集已尝试完毕")
    if updated:
        logger.info("session_end 收口未终态步骤 task=%s n=%s", task_id, updated)
    return updated


def session_end_light(store: Any, task_id: str) -> None:
    """会话结束轻量收口：与 stream 一并结束流程，不新开分析步。"""
    close_open_steps_for_session_end(store, task_id)


def run_full_reconcile_if_requested(store: Any, task_id: str) -> None:
    """仅当环境变量开启时跑重 reconcile（修复用，非正常写报路径）。"""
    if os.environ.get("HERMES_REPORT_FULL_RECONCILE", "").strip() not in {"1", "true", "yes"}:
        return
    from report_04.step_reconcile import reconcile_stuck_pipeline

    logger.info("HERMES_REPORT_FULL_RECONCILE=1，执行 reconcile_stuck_pipeline task=%s", task_id)
    reconcile_stuck_pipeline(store, task_id)
