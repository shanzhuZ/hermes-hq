"""04 写报编排引擎 v2：确定性推进步骤，减轻 Agent 空转与 Hook 超时。

原则：
- 步骤终态仅由 Hook/task_store 写入；Java 粗同步对 account_report 不写库。
- post_tool 热路径只跑轻量收口，全量 reconcile 仅 session_end + 环境变量。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from collect_01 import db
from report_04.gates import (
    can_advance_to_step5,
    can_advance_to_step7,
    get_step_status,
    is_stream_compare_ready,
    step3_profiles_terminal,
)
from report_04.orchestrator import infer_gate_step, block_tool_reason
from report_04.phases import (
    ANALYSIS_STEP_KEYS,
    PHASE_DONE,
    POST_PARENT_STEP_KEY,
    PROFILE_PARENT_STEP_KEY,
    STEP5_STREAM_TOOLS,
)

logger = logging.getLogger(__name__)

ENGINE_VERSION = "v2"

# 步骤四：距上次成功主页工具超过该秒数且无抢跑干扰时，fail-forward 跳过未尝试子节点
STEP4_QUIET_SKIP_SECONDS = 60.0


def snapshot(task_id: str) -> Dict[str, Any]:
    """给 pre_llm / 日志用的当前编排快照。"""
    gate = infer_gate_step(task_id)
    return {
        "engineVersion": ENGINE_VERSION,
        "gateStep": gate,
        "step4Terminal": step3_profiles_terminal(task_id),
        "step5": get_step_status(task_id, "step3_identity")
        or get_step_status(task_id, "step4_identity"),
        "step6": get_step_status(task_id, "step6_validated"),
        "step7": get_step_status(task_id, "step5_posts"),
        "step11": get_step_status(task_id, "step7_report"),
    }


def format_system_progress_board(task_id: str) -> str:
    """每轮注入：进度 + 下一步（v3.1：intake + 六步）。"""
    gate = infer_gate_step(task_id)
    s0 = get_step_status(task_id, "step0_intake") or "n/a"
    s1 = get_step_status(task_id, "step1_seed") or "pending"
    s2 = get_step_status(task_id, "step2_maigret") or "pending"
    s3 = get_step_status(task_id, "step3_identity") or get_step_status(
        task_id, "step4_identity"
    ) or "pending"
    s3p = get_step_status(task_id, "step3_profiles") or "pending"
    s4 = get_step_status(task_id, "step4_osint_web") or get_step_status(
        task_id, "step2_osint_web"
    ) or "pending"
    s7 = get_step_status(task_id, "step5_posts") or "pending"
    s11 = get_step_status(task_id, "step7_report") or "pending"

    if gate == "step0_intake":
        return "\n".join(
            [
                "【系统进度·输入分析】",
                f"- 步骤0 输入分析 step0_intake: {s0}",
                "【当前编排】step0_intake",
                "【下一步】分析用户输入；有社交→A，搜到链接→B 回填，确认无社交→C；"
                "必须输出 [输入分析结论]；缺链接可用有限次 web_search。",
            ]
        )

    early_gates = {
        "step1_seed",
        "step2_maigret",
        "step3_identity",
        "step3_profiles",
        "step4_identity",
    }
    if gate in early_gates and s4 not in {"running", "completed", "skipped"}:
        lines = [
            "【系统进度·前半段】",
            f"- 步骤0 输入分析 step0_intake: {s0}",
            f"- 步骤1 主账号 step1_seed: {s1}",
            f"- 步骤2 Maigret step2_maigret: {s2}",
            f"- 步骤3 认定 step3_identity: {s3}（候选主页 {s3p}）",
            f"【当前编排】{gate}",
        ]
        early_next = {
            "step1_seed": (
                "【下一步】只采主账号主页；禁止 Maigret/web_search/发文。"
            ),
            "step2_maigret": (
                "【下一步】只调 mcp_maigret_collect_accounts；禁止用 web_search 找账号。"
            ),
            "step3_identity": (
                (
                    "【下一步】先完成 3.2 候选主页佐证，暂勿输出最终认定结论。"
                    if s3p in {"pending", "running"}
                    else "【下一步】A/B 输出 [账号认定结论]；C 输出 [人物锚定结论]。"
                )
            ),
            "step4_identity": (
                "【下一步】输出 [账号认定结论]；必要时采候选主页佐证；禁止 web_search 扩账号。"
            ),
            "step3_profiles": (
                "【下一步】对已纳入认定的候选调主页工具；禁止再采种子平台；禁止发文。"
            ),
        }
        lines.append(early_next.get(gate, "【下一步】按当前编排继续；禁止跳步。"))
        return "\n".join(lines)

    lines = [
        "【系统进度·后半段】",
        f"- 步骤3 认定 step3_identity: {s3}",
        f"- 步骤4 公开信息 step4_osint_web: {s4}",
        f"- 步骤5 发文 step5_posts: {s7}",
        f"- 步骤6 报告 step7_report: {s11}",
        f"【当前编排】{gate}",
    ]
    try:
        from report_04.gates import can_run_step7_collect, posts_substantively_ready
        from report_04.step_reconcile import list_unattempted_post_platforms

        if posts_substantively_ready(task_id) or s7 in {"completed", "skipped"}:
            try:
                from report_04.gates import can_advance_to_analysis
                from report_04.video_report import format_report_wait_hint

                if not can_advance_to_analysis(task_id).get("ok"):
                    lines.append(
                        "【下一步】发文已齐，step5_posts 未终态（常为等视频）→ 保持会话；"
                        "禁止提前写八章终稿；禁止同步 mcp_video2frame_*。"
                    )
                else:
                    wait_hint = format_report_wait_hint(task_id)
                    if wait_hint:
                        lines.append(wait_hint)
                    else:
                        lines.append(
                            "【下一步】立刻一次输出八章终稿（文首标题或「一、基本情况」）；"
                            "禁止结束会话；禁止 vision。"
                        )
            except Exception:
                lines.append(
                    "【下一步】立刻一次输出八章终稿；禁止结束会话；禁止 vision。"
                )
        elif can_run_step7_collect(task_id):
            todo = list_unattempted_post_platforms(task_id) or []
            if todo:
                hints = "; ".join(
                    f"{x.get('platform')}:{x.get('tool_hint')}" for x in todo[:6]
                )
                lines.append(
                    f"【下一步】发文已开放 → 本回合必须调发文工具（{len(todo)} 个）：{hints}；"
                    "禁止只写等待句后结束会话。"
                )
            else:
                lines.append(
                    "【下一步】发文门禁已开且待采列表为空 → 保持会话或写八章终稿；禁止 done。"
                )
        elif s4 not in {"completed", "skipped"}:
            lines.append(
                "【下一步】步骤4：仅用 web_search/web_extract 为八章备料；"
                "禁止再搜社交账号；禁止发文。"
            )
        elif s3 not in {"completed", "skipped"}:
            lines.append(
                "【下一步】输出 [账号认定结论]；必要时采候选主页；禁止发文。"
            )
        else:
            lines.append(
                "【下一步】按 v3 编排继续（网页备料→发文→八章终稿）；"
                "禁止输出步骤8/9/10；禁止空等 done。"
            )
    except Exception:
        lines.append("【下一步】禁止结束会话；按当前编排继续。")
    return "\n".join(lines)


def build_report_materials_pack(task_id: str, *, max_chars: int = 6500) -> str:
    """写报前压缩材料包：已入库主页/发文/网页来源，减少模型再搜再采。"""
    lines: List[str] = [
        "【写报材料包·已入库摘要】以下材料已在库；禁止再调 web_search/发文/主页/write_file，直接据此写八章。",
    ]
    try:
        task = db.fetch_one(
            "SELECT seed_json, subject_json FROM hermes_tasks WHERE task_id=%s",
            (task_id,),
        ) or {}
        seed = {}
        try:
            import json as _json

            seed = _json.loads(task.get("seed_json") or "{}") or {}
        except Exception:
            seed = {}
        name = str(seed.get("person_name") or seed.get("account_hint") or "").strip()
        job = str(seed.get("job_title") or "").strip()
        org = str(seed.get("org") or "").strip()
        if name or job or org:
            lines.append(
                f"- 对象：{name or '（未命名）'}"
                + (f"｜职位：{job}" if job else "")
                + (f"｜机构：{org}" if org else "")
            )
        if seed.get("profile_url") or seed.get("platform"):
            lines.append(
                f"- 种子：{seed.get('platform') or ''} "
                f"{seed.get('account_hint') or seed.get('account_handle') or ''} "
                f"{seed.get('profile_url') or ''}".strip()
            )
    except Exception:
        pass

    try:
        profiles = db.fetch_all(
            """
            SELECT platform, account_id, account_handle, display_name,
                   LEFT(IFNULL(bio,''), 160) AS bio, profile_url
            FROM collect_profiles WHERE task_id=%s
            ORDER BY id ASC LIMIT 8
            """,
            (task_id,),
        ) or []
        if profiles:
            lines.append("- 已入库主页：")
            for p in profiles:
                lines.append(
                    f"  · {p.get('platform')}/{p.get('account_handle') or p.get('account_id')}"
                    f"｜{p.get('display_name') or ''}"
                    f"｜{(p.get('bio') or '').replace(chr(10), ' ')}"
                    f"｜{p.get('profile_url') or ''}"
                )
    except Exception:
        pass

    try:
        posts = db.fetch_all(
            """
            SELECT platform, account_id, published_at,
                   LEFT(IFNULL(content_text,''), 180) AS txt,
                   LEFT(IFNULL(content_url,''), 120) AS url
            FROM collect_posts WHERE task_id=%s
            ORDER BY published_at DESC, id DESC
            LIMIT 12
            """,
            (task_id,),
        ) or []
        if posts:
            lines.append(f"- 已入库发文摘要（最近 {len(posts)} 条）：")
            for p in posts:
                lines.append(
                    f"  · [{p.get('platform')}] {p.get('published_at') or ''} "
                    f"{(p.get('txt') or '').replace(chr(10), ' ')} "
                    f"{p.get('url') or ''}"
                )
        else:
            lines.append("- 已入库发文：0 条（公开表达可写未核实，或改用步骤4网页材料作证）")
    except Exception:
        pass

    try:
        import json as _json

        row = db.fetch_one(
            """
            SELECT payload_json FROM collect_phase_steps
            WHERE task_id=%s AND step_key='step4_osint_web'
            """,
            (task_id,),
        )
        payload = {}
        if row and row.get("payload_json"):
            payload = _json.loads(row.get("payload_json") or "{}") or {}
        coverage = payload.get("template_coverage") if isinstance(payload, dict) else None
        if isinstance(coverage, dict) and coverage:
            lines.append("- 步骤4网页覆盖：")
            for key, meta in coverage.items():
                if not isinstance(meta, dict):
                    continue
                status = meta.get("status") or ""
                sources = meta.get("sources") or []
                src = "；".join(str(x) for x in sources[:3]) if isinstance(sources, list) else ""
                lines.append(f"  · {key}:{status}" + (f"｜{src}" if src else ""))
    except Exception:
        pass

    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…（材料包已截断）"
    return text


def _build_agent_context_v3(task_id: str, gate: str) -> str:
    """v3.1：intake + 六步；禁止再注入旧 4.1/4.3/步骤8～10 写报路径。"""
    lines: List[str] = [
        format_system_progress_board(task_id),
        f"【04引擎 {ENGINE_VERSION}·v3】当前编排步骤：{gate}",
    ]
    if gate == "step0_intake":
        lines.append(
            "步骤0：分析用户输入并输出 [输入分析结论]（outcome: A/B/C）。"
            "A=已有社交；B=搜到链接并回填 platform/handle；C=确认无社交。"
            "B 禁止只凭同名，reason 至少写两项独立一致锚点并说明无关键冲突。"
            "只用 web_search/web_extract 找个人社交主页；禁止 Maigret；禁止写八章、禁止发文。"
        )
    elif gate == "step1_seed":
        lines.append(
            "步骤1：只采主账号主页（必须 MCP/Apify，禁止 terminal/curl）；"
            "LinkedIn→mcp_apify_harvestapi__linkedin_profile_scraper→get_actor_run→get_dataset_items；"
            "步骤1完成前严禁并行启动步骤2；禁止 Maigret/web_search/发文/写八章。"
        )
    elif gate == "step2_maigret":
        lines.append(
            "步骤2：只调 mcp_maigret_collect_accounts；禁止用 web_search 找账号。"
        )
    elif gate in {"step3_identity", "step4_identity"}:
        try:
            from report_04.intake import is_person_path

            if is_person_path(task_id):
                lines.append(
                    "步骤3（C路径）：输出 [人物锚定结论]（姓名/职位/机构消歧）；"
                    "写明未见可靠社交账号；禁止编造 handle；禁止发文、禁止写八章。"
                )
            elif get_step_status(task_id, "step3_profiles") in {"pending", "running"}:
                lines.append(
                    "步骤3：账号认定已开始；先对 Maigret 新候选采主页佐证。"
                    "候选主页父/子节点终态后再输出 [账号认定结论]；"
                    "禁止重复采种子主页、禁止 web_search 扩账号、禁止发文。"
                )
            else:
                lines.append(
                    "步骤3：候选主页佐证已收口，现在输出 [账号认定结论]；"
                    "必须分行列出 validated_accounts 与 excluded_accounts（platform|handle|profile_url|依据）；"
                    "禁止 web_search 扩账号、禁止发文、禁止写八章。"
                )
        except Exception:
            lines.append(
                "步骤3：输出 [账号认定结论]；必要时采候选主页佐证；"
                "禁止 web_search 扩账号、禁止发文、禁止写八章。"
            )
    elif gate == "step3_profiles":
        lines.append(
            "步骤3辅：对已纳入认定的候选调主页工具；禁止再采种子平台；禁止发文。"
        )
    elif gate in {"step4_osint_web", "step2_osint_web"}:
        try:
            from report_04.intake import is_person_path

            if is_person_path(task_id):
                lines.append(
                    "步骤4（C路径·主产能）：加大 web_search/web_extract，"
                    "按八章模板深挖官网/新闻/机构页；禁止编造社交账号；禁止发文；禁止写八章终稿。"
                )
            else:
                lines.append(
                    "步骤4：仅用 web_search/web_extract 为八章备料；"
                    "禁止再搜社交账号；禁止发文；禁止写八章终稿。"
                )
        except Exception:
            lines.append(
                "步骤4：仅用 web_search/web_extract 为八章备料；"
                "禁止再搜社交账号；禁止发文；禁止写八章终稿。"
            )
        try:
            from report_04.sink import format_web_coverage_hint

            lines.append(format_web_coverage_hint(task_id))
        except Exception:
            lines.append(
                "步骤4按六类模板资料组合检索：基本情况、在职在岗、人脉、政治立场、"
                "污点劣迹、公开表达；无结果也须明确完成该主题检索。"
            )
    elif gate == "step5_posts":
        lines.append(
            "步骤5：对已认定账号调用发文工具；禁止提前写八章；"
            "禁止输出步骤8/9/10 旧专题。"
        )
        try:
            from report_04.step_reconcile import list_unattempted_post_platforms

            todo = list_unattempted_post_platforms(task_id) or []
            if todo:
                lines.append(f"【必须立即调用】共 {len(todo)} 个平台：")
                for item in todo[:12]:
                    lines.append(
                        f"- {item.get('platform')}: {item.get('tool_hint')}"
                    )
            else:
                wait_hint = ""
                try:
                    from report_04.video_report import format_report_wait_hint

                    wait_hint = format_report_wait_hint(task_id)
                except Exception:
                    wait_hint = ""
                if wait_hint:
                    lines.append(wait_hint)
                else:
                    lines.append(
                        "发文工具均已尝试；父壳终态后立刻一次输出八章终稿"
                        "（文首标题或「一、基本情况」）。禁止步骤8/9/10 旧专题。"
                    )
        except Exception:
            pass
    elif gate == "step7_report":
        wait_hint = ""
        try:
            from report_04.video_report import format_report_wait_hint

            wait_hint = format_report_wait_hint(task_id)
        except Exception:
            wait_hint = ""
        if wait_hint:
            lines.append(wait_hint)
        else:
            lines.append(
                "步骤6：立刻在对话中一次输出八章公开资料核查报告（见 Skill 骨架）。"
                "第一行写「# {姓名} 公开资料核查报告」；有可核验本人图则附 Markdown 图片及来源，无图整段省略。"
                "八章齐全即可收口；缺资料写「未核实」，禁止再搜、再采、write_file、拆旧专题。"
            )
            try:
                lines.append(build_report_materials_pack(task_id))
            except Exception as exc:
                logger.warning("写报材料包注入失败 task=%s: %s", task_id, exc)
    else:
        lines.append(
            "按 v3 六步继续；禁止输出步骤8/9/10 旧专题；禁止空等 done。"
        )
    return "\n".join(lines)


def build_agent_context(task_id: str) -> Optional[str]:
    """注入 Agent：系统进度看板 + 当前 gate + 应做之事。"""
    gate = infer_gate_step(task_id)
    try:
        from report_04.gates import is_v3_report_tree

        if is_v3_report_tree(task_id):
            return _build_agent_context_v3(task_id, gate)
    except Exception:
        pass
    lines: List[str] = [
        format_system_progress_board(task_id),
        f"【04引擎 {ENGINE_VERSION}】当前编排步骤：{gate}",
    ]

    if gate == "step1_seed":
        lines.append(
            "步骤1：必须先调用种子平台主页工具落库；"
            "禁止跳写步骤5 [文本核验结论]、禁止 session_search、禁止发文。"
        )
    elif gate == "step2_osint_web":
        lines.append(
            "步骤2：只调 mcp_maigret_collect_accounts(username=种子handle)；"
            "禁止跳写步骤5核验。"
        )
    elif gate == "step2_osint_web":
        lines.append(
            "步骤3：网页线索检索；禁止跳写步骤5核验/发文。"
        )
    elif gate == "step3_profiles":
        lines.append(
            "步骤3（账号主页采集）：须对线索发现（步骤2 Maigret + 步骤3 网页）产出的"
            "每个可采集候选平台调用主页工具；禁止因「与种子不相似」跳过；"
            "相似度只在步骤6认定。禁止社工库/发文/vision；采不到或失败再 skip。"
        )
        open_rows = db.fetch_all(
            """
            SELECT step_key, status FROM collect_phase_steps
            WHERE task_id=%s AND parent_step_key=%s
              AND status IN ('pending', 'running')
            ORDER BY step_order, step_key
            """,
            (task_id, PROFILE_PARENT_STEP_KEY),
        )
        if open_rows:
            from report_04.phases import APIFY_TOOL_PLATFORM, TOOL_PLATFORM

            lines.append(f"【本回合必须处理】未终态主页子步 {len(open_rows)} 个：")
            rev_apify = {p: t for t, p in APIFY_TOOL_PLATFORM.items()}
            rev_mcp = {}
            for t, p in TOOL_PLATFORM.items():
                if p not in rev_apify and "get_user_tweets" not in t and "feeds" not in t and "analyze_channel" not in t:
                    rev_mcp.setdefault(p, t)
            for r in open_rows[:12]:
                sk = str(r.get("step_key") or "")
                plat = sk.replace("step3_profile_", "", 1) if sk.startswith("step3_profile_") else sk
                hint = rev_mcp.get(plat) or rev_apify.get(plat) or f"Apify/MCP 主页工具({plat})"
                if plat in rev_apify:
                    hint = f"{rev_apify[plat]} → get_actor_run → get_dataset_items"
                lines.append(f"- {sk}: {hint}")
        lines.append(
            "全部子步终态后系统自动跑 4.1→4.2→4.3；未完成步骤3前调用社工库会被拦截。"
        )

    elif gate == "step4_identity":
        from report_04.sink import _pending_image_stream_lines  # noqa: PLC0415 — 复用既有 URL 列表

        pending = _pending_image_stream_lines(task_id)
        s5 = get_step_status(task_id, "step4_identity")
        if s5 in {"completed", "skipped"}:
            lines.append(
                "步骤5已系统收口，禁止再 vision/OCR；"
                "禁止结束会话、禁止写「等待系统/会话保持」。"
                "系统推进 4.2/4.3 后，本会话必须立刻调发文工具。"
            )
        elif not step3_profiles_terminal(task_id):
            pend = None
            try:
                from report_04.gates import _step3_profile_children_pending

                pend = _step3_profile_children_pending(task_id)
            except Exception:
                pend = "step3_profile_*"
            lines.append(
                f"步骤4未全终态（仍有 {pend or 'pending/running'}），请先完成/跳过该平台主页，再并行 vision。"
            )
        elif pending:
            lines.append(
                f"步骤5：请本回合并行 {len(pending)} 次 vision_analyze（一次齐发），image_url 必须用："
            )
            lines.extend(pending[:8])
        else:
            lines.append(
                "步骤5：图片流已齐或由系统管线处理；请输出 [文本核验结论]（若尚未输出）。"
                "结论只陈述证据；禁止写「暂不启动步骤6/不宜纳入 validated」——"
                "4.2 由系统自动收敛（种子必进 validated）。"
                "禁止写「等待系统/会话保持中」并 done；保持会话，门禁放行后立刻调发文。"
            )

    elif gate == "step6_validated":
        lines.append(
            "步骤6（4.2）：系统正在/即将收敛可信账号（非 Agent 决定是否启动）；"
            "禁止输出「等待系统/不启动步骤6」后 done；"
            "系统收口后同一会话必须立刻进入发文。"
        )

    elif gate == "step6_osint_es":
        from report_04.osint_es import format_pending_urls_for_agent

        pending = format_pending_urls_for_agent(task_id)
        lines.append(
            "步骤4.3 社工库核验：主路径由系统自动查 ES；"
            "若下列仍有待查 URL，可补调 mcp_es_search_search_country_wise"
            "（query_text=profile_url，按需 field；可选 person_name）；"
            "禁止 search_facebook/search_worldpeople；禁止发文工具。"
            "禁止结束会话空等。"
        )
        if pending:
            lines.append(f"待查 URL（{len(pending)}）：")
            lines.extend(pending[:20])
        else:
            lines.append(
                "待查 URL 已由系统查完或无可查 URL；"
                "可选输出 [社工库核验结论]。4.7 PDL 与本步并行，不依赖社工库成败。"
            )
        # 4.3 已终态：催 4.7 / 发文
        if get_step_status(task_id, "step6_osint_es") in {"completed", "skipped", "failed"}:
            sp = get_step_status(task_id, "step6_pdl")
            if sp not in {"completed", "skipped", "failed"}:
                lines.append(
                    "【下一步】4.3 已终态（失败/跳过也算），系统正在/即将跑 4.7 PDL；"
                    "可补调 mcp_pdl_person_search_person(social_link=profile_url)；禁止发文、禁止 done。"
                )
            else:
                try:
                    from report_04.step_reconcile import list_unattempted_post_platforms

                    todo7 = list_unattempted_post_platforms(task_id)
                    if todo7:
                        lines.append(
                            "【下一步硬强制】步骤7须先对下列 validated 调用发文工具"
                            f"（{len(todo7)} 个尚未尝试），禁止直接写分析/终稿："
                        )
                        for item in todo7[:10]:
                            lines.append(
                                f"- {item.get('platform')}: {item.get('tool_hint')}"
                            )
                except Exception:
                    pass

    elif gate == "step6_pdl":
        lines.append(
            "步骤4.7 全球人员信息检索（PDL）：与 4.3 并行，主路径由系统自动查；"
            "可补调 mcp_pdl_person_search_person(social_link=validated 的 profile_url)；"
            "无命中会 skipped，不阻塞发文。禁止发文工具，禁止结束会话。"
        )
        try:
            from report_04.pdl_enrich import list_pdl_query_targets

            targets = list_pdl_query_targets(task_id)
            if targets:
                lines.append(f"可查 URL（{len(targets)}）：")
                for item in targets[:10]:
                    lines.append(
                        f"- {item.get('platform')}/{item.get('account_id')}: {item.get('profile_url')}"
                    )
        except Exception:
            pass
        if get_step_status(task_id, "step6_pdl") in {"completed", "skipped"}:
            try:
                from report_04.step_reconcile import list_unattempted_post_platforms

                todo7 = list_unattempted_post_platforms(task_id)
                if todo7:
                    lines.append(
                        "【下一步硬强制】4.7 已终态，步骤7须立刻调发文工具："
                    )
                    for item in todo7[:10]:
                        lines.append(
                            f"- {item.get('platform')}: {item.get('tool_hint')}"
                        )
            except Exception:
                pass

    elif gate == "step5_posts":
        # 步骤7 发文（勿称「步骤5/UI步骤5」）
        s7 = get_step_status(task_id, "step5_posts")
        open_posts = db.fetch_all(
            """
            SELECT step_key, status FROM collect_phase_steps
            WHERE task_id=%s AND parent_step_key=%s
              AND status IN ('pending', 'running')
            ORDER BY step_order, step_key
            """,
            (task_id, POST_PARENT_STEP_KEY),
        )
        open_keys = [str(r.get("step_key") or "") for r in (open_posts or [])]
        if s7 in {"pending", None, ""}:
            lines.append(
                "【步骤7发文·待启动】4.3/4.7 已终态，发文父节点等待你调用工具后才会 running。"
                "本回合必须对下列 validated 发起发文工具；"
                "禁止只写步骤5核验/等待系统、禁止进分析/终稿、禁止结束会话。"
            )
        else:
            lines.append(
                "【步骤7发文·硬强制】本回合继续对各平台调用发文工具。"
                "禁止输出分析/终稿；允许工具已调用但失败或 0 条再 skip。主页≠发文。"
            )
        try:
            from report_04.step_reconcile import list_unattempted_post_platforms

            todo = list_unattempted_post_platforms(task_id)
            if todo:
                lines.append(
                    f"【必须立即调用·禁止空过】共 {len(todo)} 个平台，请本回合并行发起工具："
                )
                for item in todo[:12]:
                    lines.append(
                        f"- {item.get('platform')}: {item.get('tool_hint')}"
                    )
            else:
                wait_hint = ""
                try:
                    from report_04.video_report import format_report_wait_hint

                    wait_hint = format_report_wait_hint(task_id)
                except Exception:
                    wait_hint = ""
                if wait_hint:
                    lines.append(
                        "发文工具均已尝试。" + wait_hint
                        + "禁止再调 vision；禁止回写步骤5/6/4.3。"
                    )
                else:
                    lines.append(
                        "发文工具均已尝试；系统将关 step5_posts 父壳。"
                        "父壳终态后立刻一次输出八章公开资料核查报告（文首标题或「一、基本情况」）。"
                        "禁止再写步骤8/9/10 旧专题；禁止再调 vision；禁止回写已终态步骤。"
                    )
        except Exception:
            pass
        if open_keys:
            lines.append(
                "仍有未完成发文子步："
                + ", ".join(open_keys[:12])
                + "。必须继续采集，禁止结束会话空等。"
            )
        lines.append(
            "发文入库后若有可下载视频，Hook 会挂 step5_video_* 后台分析："
            "不挡发文子步 completed，但挡住 step5_posts 父壳收口；"
            "须等父壳终态后直接写八章终稿；禁止输出步骤8/9/10；禁止同步 mcp_video2frame_*。"
        )

    elif gate in ANALYSIS_STEP_KEYS or gate == "step7_report":
        try:
            from report_04.step_reconcile import list_unattempted_post_platforms

            leftover = list_unattempted_post_platforms(task_id)
            if leftover:
                lines.append(
                    "【违规风险】仍有 validated 平台未尝试发文工具，禁止写八章终稿；"
                    "请立刻回调发文工具："
                )
                for item in leftover[:8]:
                    lines.append(
                        f"- {item.get('platform')}: {item.get('tool_hint')}"
                    )
        except Exception:
            pass
        lines.append(
            f"当前 task_id={task_id}。图片资产由系统 Hook 后台兜底；"
            "禁止 Agent 自行执行 image_pipeline；"
            "禁止在终稿前缀/正文写管线元叙述。树上无六专题：发文齐后直接写八章。"
        )
        try:
            from report_04.gates import format_step8_wait_hint, step8_blocks_write

            if step8_blocks_write(task_id):
                s8_hint = format_step8_wait_hint(task_id)
                if s8_hint:
                    lines.append(s8_hint)
                lines.append("当前须 hold：禁止输出终稿；图片流收口后系统再催 write。")
                return "\n".join(lines)
        except Exception:
            pass
        wait_hint = ""
        try:
            from report_04.video_report import format_report_wait_hint

            wait_hint = format_report_wait_hint(task_id)
        except Exception:
            wait_hint = ""
        if wait_hint:
            lines.append(wait_hint)
        elif gate == "step7_report":
            lines.append(
                "步骤6：一次输出八章公开资料核查报告（见 Skill 骨架）。"
                "第一行必须写「# {姓名} 公开资料核查报告」。"
                "已有可核验本人图片 URL 时在标题下插入 Markdown 图片及来源；无图则整段省略。"
                "勿在第一节前写进度/管线句。"
                "必须完整保留 Skill 骨架的固定章节与二级项；无资料写未核实，禁止删项或合并。"
                "综合步骤2～5证据；无可靠来源写「未核实」；允许带来源链接。"
                "第七章写完整身份核验与综合结论；末附「八、主要来源」。"
            )
        elif gate in ANALYSIS_STEP_KEYS:
            lines.append(
                "请直接撰写八章终稿；v3 无步骤8/9/10 专题，禁止再输出旧研判空壳。"
            )

    return "\n".join(lines)


def advance_collision_phase(store: Any, task_id: str, *, max_rounds: int = 4) -> None:
    """压缩「四、关联碰撞」空窗：同轮尽量连推 4.1→4.2→4.3。"""
    from report_04.gates import is_v3_report_tree

    if is_v3_report_tree(task_id):
        return
    for _ in range(max(1, int(max_rounds))):
        before = (
            get_step_status(task_id, "step4_identity"),
            get_step_status(task_id, "step6_validated"),
            get_step_status(task_id, "step6_osint_es"),
            get_step_status(task_id, "step6_pdl"),
        )
        try:
            _auto_step5_step6(store, task_id)
        except Exception as exc:
            logger.warning("advance_collision 失败 task=%s: %s", task_id, exc)
            break
        after = (
            get_step_status(task_id, "step4_identity"),
            get_step_status(task_id, "step6_validated"),
            get_step_status(task_id, "step6_osint_es"),
            get_step_status(task_id, "step6_pdl"),
        )
        if after == before:
            break
        # 4.3/4.7 终态后才停连推（failed 也算；旧任务无 PDL 行则只看 4.3）
        if after[2] in {"completed", "skipped", "failed"} and (
            after[3] is None or after[3] in {"completed", "skipped", "failed"}
        ):
            break


def build_post_llm_followup(task_id: str) -> str:
    """post_llm 回注：进度看板 + 下一步动作 + 禁止 done。"""
    from report_04.session_continue import build_next_action_hint

    board = format_system_progress_board(task_id)
    hint = build_next_action_hint(task_id)
    tail = (
        "\n【写报硬约束】禁止以「等待系统/会话保持/等步骤6/4.3」结束本轮。"
        "无工具可调时保持会话；门禁放行后立刻调发文或写分析/终稿。"
    )
    if hint:
        return board + "\n" + hint + tail
    return board + tail


def enrich_block_reason(task_id: str, reason: str) -> str:
    ctx = build_agent_context(task_id)
    if not ctx:
        return reason
    return reason + "\n\n" + ctx


def ensure_maigret_closed_if_tool_done(store: Any, task_id: str) -> bool:
    """已有成功 mcp_maigret_collect_accounts 但 step2_maigret 仍卡 running → 收口。"""
    try:
        from report_04.intake import intake_open

        if intake_open(task_id):
            return False
    except Exception:
        pass
    from collect_01 import db
    from report_04.phases import MAIGRET_STEP_KEY

    cur = get_step_status(task_id, MAIGRET_STEP_KEY)
    if cur in {"completed", "skipped", "failed"}:
        return False
    row = db.fetch_one(
        """
        SELECT COUNT(*) AS c FROM hermes_tool_outputs
        WHERE task_id=%s AND tool_name='mcp_maigret_collect_accounts' AND status='success'
        """,
        (task_id,),
    )
    if int((row or {}).get("c") or 0) < 1:
        return False
    store.set_step_status(
        task_id,
        MAIGRET_STEP_KEY,
        "completed",
        message="Maigret 已成功入库，步骤状态兜底收口",
    )
    logger.info("兜底收口 step2_maigret task=%s prev=%s", task_id, cur)
    return True


def apply_identity_conclusion_from_thoughts(store: Any, task_id: str) -> bool:
    """思考流已写出 [账号认定结论] 但 step3 未收口时，从 hermes_thought_events 兜底落库。"""
    from collect_01 import db
    from report_04.gates import identity_step_terminal
    from report_04.phases import STREAM_TEXT_CONCLUSION_MARKER
    from report_04.stream_steps import apply_text_conclusion_from_assistant

    try:
        from report_04.intake import intake_open

        if intake_open(task_id):
            return False
    except Exception:
        pass
    if identity_step_terminal(task_id):
        return False
    row = db.fetch_one(
        """
        SELECT content FROM hermes_thought_events
        WHERE task_id=%s AND content LIKE %s
        ORDER BY seq DESC
        LIMIT 1
        """,
        (task_id, f"%{STREAM_TEXT_CONCLUSION_MARKER}%"),
    )
    content = str((row or {}).get("content") or "").strip()
    if not content or STREAM_TEXT_CONCLUSION_MARKER not in content:
        return False
    ok = apply_text_conclusion_from_assistant(store, task_id, content)
    if ok:
        logger.info("从思考流兜底落库账号认定结论 task=%s", task_id)
    return bool(ok)


def ensure_v3_identity_started(store: Any, task_id: str) -> bool:
    """Maigret 终态后立即点亮 3.1；3.2 候选主页作为认定中的佐证子任务。"""
    from report_04.gates import is_v3_report_tree

    if not is_v3_report_tree(task_id):
        return False
    if not can_advance_to_step5(task_id).get("ok"):
        return False
    cur = get_step_status(task_id, "step3_identity")
    if cur in {"completed", "skipped", "failed", "running"}:
        return False
    # 先点亮 3.1，再允许 3.2 terminal，保证前端与 finished_at 不出现倒序。
    store.set_step_status(
        task_id,
        "step3_identity",
        "running",
        message="账号认定中（候选主页作为佐证）",
    )
    try:
        store.materialize_step4_from_candidates(task_id)
    except Exception as exc:
        logger.warning("v3 点亮认定前物化候选失败 task=%s: %s", task_id, exc)
    return True


def run_post_tool_light(store: Any, task_id: str) -> None:
    """post_tool 末尾：毫秒～百毫秒级，禁止 reconcile_stuck_pipeline。"""
    from report_04.gates import is_v3_report_tree
    from report_04.step_reconcile import (
        close_collect_parent_if_ready,
        ensure_osint_not_premature,
        ensure_step4_parent_not_premature,
        ensure_step5_not_premature,
        ensure_step6_not_premature,
        ensure_step7_awaits_agent_tool,
        ensure_step7_parent_active,
        ensure_step7_parent_not_premature,
        maybe_close_abandoned_step4,
    )

    # 长工具调用期间可能已在思考流写出 [输入分析结论]，此处兜底收口
    try:
        from report_04.intake import try_apply_intake_from_thoughts

        try_apply_intake_from_thoughts(store, task_id)
    except Exception as exc:
        logger.warning("engine post_tool intake 兜底失败 task=%s: %s", task_id, exc)

    try:
        ensure_maigret_closed_if_tool_done(store, task_id)
    except Exception as exc:
        logger.warning("engine maigret 兜底收口失败 task=%s: %s", task_id, exc)
    try:
        from report_04.sink import _ensure_maigret_parent_lit

        _ensure_maigret_parent_lit(store, task_id)
    except Exception as exc:
        logger.warning("engine 补点亮 Maigret 父壳失败 task=%s: %s", task_id, exc)

    v3 = False
    try:
        v3 = is_v3_report_tree(task_id)
    except Exception:
        v3 = False

    if v3:
        try:
            ensure_v3_identity_started(store, task_id)
        except Exception as exc:
            logger.warning("engine 点亮 v3 账号认定失败 task=%s: %s", task_id, exc)

    try:
        ensure_step4_parent_not_premature(store, task_id)
        # v3 无旧 4.1/4.2/4.3 碰撞链；旧 ensure 会误 kickoff Perplexity 拖死 Hook
        if not v3:
            ensure_step5_not_premature(store, task_id)
            ensure_step6_not_premature(store, task_id)
            ensure_osint_not_premature(store, task_id)
        ensure_step7_parent_not_premature(store, task_id)
        # 晚到发文子节点时回开已 completed 的 step5_posts（及 phase_content 壳）
        ensure_step7_parent_active(store, task_id)
        # 违规空过的发文子步回开为 pending（父节点不强制 running）
        from report_04.step_reconcile import reopen_unattempted_empty_skipped_posts

        reopen_unattempted_empty_skipped_posts(store, task_id)
        # 无发文工具却 running：降回 pending，禁止抢跑甩开 stream
        ensure_step7_awaits_agent_tool(store, task_id)
    except Exception as exc:
        logger.warning("engine ensure parent 失败 task=%s: %s", task_id, exc)

    # 步骤3：有进展超时才 fail-forward；抢跑 4.3 时不 skip（由 pre_tool 拉回）
    if not v3:
        try:
            maybe_close_abandoned_step4(
                store, task_id, min_quiet_seconds=STEP4_QUIET_SKIP_SECONDS, force=False
            )
        except Exception as exc:
            logger.warning("engine step4 收口失败 task=%s: %s", task_id, exc)

    try:
        close_collect_parent_if_ready(
            store, task_id, PROFILE_PARENT_STEP_KEY, "候选主页采集已尝试完毕"
        )
        close_collect_parent_if_ready(
            store, task_id, POST_PARENT_STEP_KEY, "发文采集已尝试完毕"
        )
    except Exception as exc:
        logger.warning("engine close parent 失败 task=%s: %s", task_id, exc)

    # 候选主页已收口后，才允许思考流里的认定结论完成 3.1。
    try:
        apply_identity_conclusion_from_thoughts(store, task_id)
    except Exception as exc:
        logger.warning("engine 认定结论思考流兜底失败 task=%s: %s", task_id, exc)

    # 认定后写可信清单（v3 不走旧 _auto_step5_step6）
    try:
        from report_04.gates import identity_step_terminal

        if identity_step_terminal(task_id):
            store.run_validated_accounts(task_id)
    except Exception as exc:
        logger.warning("engine 可信清单失败 task=%s: %s", task_id, exc)

    if not v3:
        _auto_step5_step6(store, task_id)

    try:
        from report_04.orchestrator import on_post_tool_step7_close_parent

        on_post_tool_step7_close_parent(store, task_id)
    except Exception as exc:
        logger.warning("engine step7 close 失败 task=%s: %s", task_id, exc)

    # [COLLISION_DEMO_FAKE] 工具后也跑假节点补救（不依赖下一轮 LLM）— 正式版删除
    try:
        from report_04.collision_demo_steps import reconcile_collision_demo_steps

        reconcile_collision_demo_steps(store, task_id)
    except Exception as exc:
        logger.warning("[COLLISION_DEMO_FAKE] post_tool heal 失败 task=%s: %s", task_id, exc)


def run_pre_llm_auto(store: Any, task_id: str) -> None:
    """每轮 LLM 前：推进可自动完成的步骤。

    v3 必须轻量：禁止旧碰撞连推 / 假节点 / 同步 Perplexity，否则 Hook 易撞 120s。
    """
    from report_04.gates import is_v3_report_tree

    try:
        if is_v3_report_tree(task_id):
            # 输入已含社交线索时自动收口 step0=A
            try:
                from report_04.intake import try_autocomplete_intake_from_seed
                from report_04.gates import get_step_status as _gst
                from report_04.phases import INTAKE_STEP_KEY

                from report_04.intake import try_apply_intake_from_thoughts

                try_autocomplete_intake_from_seed(store, task_id)
                try_apply_intake_from_thoughts(store, task_id)
                if _gst(task_id, INTAKE_STEP_KEY) == "pending":
                    store.set_step_status(
                        task_id,
                        INTAKE_STEP_KEY,
                        "running",
                        message="分析用户输入…",
                    )
            except Exception as exc:
                logger.warning("pre_llm v3 intake 兜底失败 task=%s: %s", task_id, exc)
            # 仅兜底状态，不跑完整 post_tool_light（远程库往返多）
            try:
                ensure_maigret_closed_if_tool_done(store, task_id)
            except Exception as exc:
                logger.warning("pre_llm v3 maigret 兜底失败 task=%s: %s", task_id, exc)
            try:
                from report_04.sink import _ensure_maigret_parent_lit

                _ensure_maigret_parent_lit(store, task_id)
            except Exception as exc:
                logger.warning("pre_llm v3 补点亮 Maigret 父壳失败 task=%s: %s", task_id, exc)
            try:
                ensure_v3_identity_started(store, task_id)
            except Exception as exc:
                logger.warning("pre_llm v3 点亮账号认定失败 task=%s: %s", task_id, exc)
            try:
                apply_identity_conclusion_from_thoughts(store, task_id)
            except Exception as exc:
                logger.warning("pre_llm v3 认定兜底失败 task=%s: %s", task_id, exc)
            try:
                from report_04.gates import identity_step_terminal

                if identity_step_terminal(task_id):
                    store.run_validated_accounts(task_id)
            except Exception as exc:
                logger.warning("pre_llm v3 可信清单失败 task=%s: %s", task_id, exc)
            _try_finalize_report(store, task_id, light_only=True)
            return
    except Exception as exc:
        logger.warning("engine pre_llm v3 判定失败 task=%s: %s", task_id, exc)

    run_post_tool_light(store, task_id)
    advance_collision_phase(store, task_id, max_rounds=3)
    # [COLLISION_DEMO_FAKE] 假节点超时/丢线程补救 — 正式版删除
    try:
        from report_04.collision_demo_steps import reconcile_collision_demo_steps

        reconcile_collision_demo_steps(store, task_id)
    except Exception as exc:
        logger.warning("[COLLISION_DEMO_FAKE] pre_llm heal 失败 task=%s: %s", task_id, exc)
    _try_finalize_report(store, task_id, light_only=True)


def run_session_finalize_light(
    store: Any,
    task_id: str,
    *,
    reason: str = "会话结束：Agent stream 已结束",
) -> None:
    """session_end：与 stream 一并结束流程（收口未终态步骤，禁止新开分析 running）。"""
    from report_04.task_store import _reconcile_report_post_child_steps
    from report_04.step_reconcile import (
        close_collect_parent_if_ready,
        reconcile_step4_and_step7_children,
        reconcile_step7_from_post_tools,
    )
    from report_04.orchestrator import close_open_steps_for_session_end

    # [COLLISION_DEMO_FAKE] 会话结束前强制收口超时假节点 — 正式版删除
    try:
        from report_04.collision_demo_steps import reconcile_collision_demo_steps

        reconcile_collision_demo_steps(store, task_id)
    except Exception as exc:
        logger.warning("[COLLISION_DEMO_FAKE] session heal 失败 task=%s: %s", task_id, exc)

    _auto_step5_step6(store, task_id)
    _reconcile_report_post_child_steps(store, task_id)
    try:
        reconcile_step7_from_post_tools(store, task_id)
        reconcile_step4_and_step7_children(store, task_id)
    except Exception as exc:
        logger.warning("engine session reconcile children 失败 task=%s: %s", task_id, exc)

    store.reconcile_collect_child_steps(task_id)
    close_collect_parent_if_ready(store, task_id, POST_PARENT_STEP_KEY, "发文采集已尝试完毕")
    # stream 已结束：未终态步骤全部收口，不再 advance_to_analysis（否则会空挂 running）
    close_open_steps_for_session_end(store, task_id, reason=reason)
    if get_step_status(task_id, "step5_posts") in {"completed", "skipped"}:
        try:
            from report_04.image_assets import spawn_second_image_pipeline

            spawn_second_image_pipeline(task_id, store=store)
        except Exception as exc:
            logger.warning("session_finalize 后台第二次图片管线失败 task=%s: %s", task_id, exc)


def _prepare_step7_after_osint(store: Any, task_id: str) -> None:
    """4.3 终态后：仅预建发文子节点，父节点保持 pending。

    禁止在此把 step5_posts / phase_content 标成 running——须等 Agent 真正调用发文工具
   （sink.start_step7_if_ready），避免 stream 还在 4.1 叙述时树上发文已抢跑。
    """
    from report_04.gates import can_run_step7_collect

    if not can_run_step7_collect(task_id):
        return
    try:
        store.prepare_step7_children_pending(task_id)
    except Exception as exc:
        logger.warning("engine prepare_step7 失败 task=%s: %s", task_id, exc)
    # 纠正误抢跑：running 但无任何发文工具/子步 running → 降回 pending
    try:
        from report_04.step_reconcile import ensure_step7_awaits_agent_tool

        ensure_step7_awaits_agent_tool(store, task_id)
    except Exception as exc:
        logger.warning("engine ensure_step7_awaits_agent 失败 task=%s: %s", task_id, exc)


def _auto_step5_step6(store: Any, task_id: str) -> None:
    """系统自动推进，但每轮最多推一档，避免甩开 Agent/stream。

    档位：4.1 kickoff/settle → 4.2 validated → 4.3 osint → 预建发文子节点（不点亮 running）。
    """
    from report_04.gates import is_v3_report_tree

    if is_v3_report_tree(task_id):
        return
    if not can_advance_to_step5(task_id).get("ok"):
        return

    s5 = get_step_status(task_id, "step4_identity")
    if s5 not in {"completed", "skipped"}:
        if step3_profiles_terminal(task_id):
            store.kickoff_step5_if_ready(task_id)
        if get_step_status(task_id, "step4_identity") == "running" and is_stream_compare_ready(
            task_id
        ):
            try:
                from report_04.sink import _try_complete_step5_if_settled

                _try_complete_step5_if_settled(store, task_id)
            except Exception as exc:
                logger.warning("engine step5 settle 失败 task=%s: %s", task_id, exc)
        return  # 本轮只推 4.1

    if get_step_status(task_id, "step6_validated") != "completed":
        try:
            store.run_validated_accounts(task_id)
            logger.info("engine 自动步骤6 task=%s", task_id)
        except Exception as exc:
            logger.warning("engine run_validated 失败 task=%s: %s", task_id, exc)
        # 4.2 仍未终态：本轮停；若刚完成则继续推 4.3（系统活，不点亮发文）
        if get_step_status(task_id, "step6_validated") != "completed":
            return

    # 4.2 已完成：4.3 与 4.7 并行 kickoff（PDL 不依赖社工库成败）
    try:
        from report_04.osint_es import kickoff_osint_if_ready, maybe_fail_forward_stale_osint
        from report_04.pdl_enrich import kickoff_pdl_if_ready, maybe_fail_forward_stale_pdl

        # 先推 4.7，避免卡在常失败的 4.3 同步管线上
        kickoff_pdl_if_ready(store, task_id)
        maybe_fail_forward_stale_pdl(store, task_id, min_wait_seconds=180)
        kickoff_osint_if_ready(store, task_id)
        maybe_fail_forward_stale_osint(store, task_id, min_wait_seconds=120.0)
    except Exception as exc:
        logger.warning("engine kickoff/fail-forward osint/pdl 失败 task=%s: %s", task_id, exc)
    _prepare_step7_after_osint(store, task_id)


def _try_finalize_report(store: Any, task_id: str, *, light_only: bool) -> None:
    """终稿已 completed 时把任务标 completed（并可选轻量 finalize）。"""
    if get_step_status(task_id, "step7_report") != "completed":
        return
    task = store.get_task(task_id) or {}
    if str(task.get("status") or "") in {"completed", "failed"}:
        return
    has_summary = db.fetch_one(
        "SELECT id FROM hermes_user_dialogues WHERE task_id=%s AND msg_type='summary' LIMIT 1",
        (task_id,),
    )
    if not has_summary:
        return
    if light_only:
        db.execute(
            """
            UPDATE hermes_tasks
            SET status='completed', current_phase=%s,
                finished_at=COALESCE(finished_at, NOW(3)), updated_at=NOW(3)
            WHERE task_id=%s AND status NOT IN ('failed', 'cancelled')
            """,
            (PHASE_DONE, task_id),
        )
        logger.info("engine 终稿已出，任务标 completed task=%s", task_id)
        return
    store.finalize_task(task_id)


def pre_tool_allowed(task_id: str, tool_name: str, *, phase: Optional[str] = None) -> Optional[str]:
    """统一 pre_tool：返回 block reason（含引擎指引）。"""
    if not tool_name:
        return None
    # sink 里还有更细的门禁，此处只做编排白名单
    reason = block_tool_reason(task_id, tool_name, phase=phase)
    if reason:
        return enrich_block_reason(task_id, reason)
    if tool_name in STEP5_STREAM_TOOLS and get_step_status(task_id, "step4_identity") in {
        "completed",
        "skipped",
    }:
        gate = infer_gate_step(task_id)
        if gate == "step5_posts":
            tip = "当前为步骤5发文：禁止 vision；请调发文工具；父壳终态后写八章终稿。"
        elif gate in ANALYSIS_STEP_KEYS or gate == "step7_report":
            tip = "当前为写报阶段：禁止 vision；请直接输出八章终稿（禁止步骤8/9/10 旧专题）。"
        elif gate in {"step6_validated", "step6_osint_es", "step6_pdl"}:
            tip = "当前为旧碰撞/社工库阶段：禁止 vision；保持会话，门禁放行后立刻调发文工具。"
        else:
            tip = "图片流已收口，禁止再 vision/OCR；请按当前编排步骤继续。"
        return enrich_block_reason(task_id, f"图片流已收口，禁止再调用 vision/OCR。{tip}")
    return None


def full_reconcile_enabled() -> bool:
    return os.environ.get("HERMES_REPORT_FULL_RECONCILE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
