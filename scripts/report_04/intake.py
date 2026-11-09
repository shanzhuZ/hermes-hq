# -*- coding: utf-8 -*-
"""步骤0 输入分析（phase_intake / step0_intake）：分流 A/B/C 并回填 seed。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from collect_01 import db
from report_04.gates import get_step_status
from report_04.phases import (
    INTAKE_STEP_KEY,
    MAIGRET_STEP_KEY,
    PHASE_INTAKE_SHELL,
    POST_PARENT_STEP_KEY,
    PROFILE_PARENT_STEP_KEY,
    seed_agent_title,
)
from common.source_tag import source_tag_json

logger = logging.getLogger(__name__)

INTAKE_CONCLUSION_MARKER = "[输入分析结论]"
PERSON_ANCHOR_MARKER = "[人物锚定结论]"

# step0 内搜链接的次数帽（与 step4 备料分开计）
INTAKE_MAX_WEB_SEARCH = 8
INTAKE_MAX_WEB_TOOLS = 12


def load_seed(task_id: str) -> Dict[str, Any]:
    row = db.fetch_one("SELECT seed_json FROM hermes_tasks WHERE task_id=%s", (task_id,))
    try:
        seed = json.loads((row or {}).get("seed_json") or "{}")
    except Exception:
        seed = {}
    return seed if isinstance(seed, dict) else {}


def save_seed(task_id: str, seed: Dict[str, Any]) -> None:
    db.execute(
        "UPDATE hermes_tasks SET seed_json=%s, updated_at=NOW(3) WHERE task_id=%s",
        (db.json_dumps(seed), task_id),
    )


def has_intake_step(task_id: str) -> bool:
    return get_step_status(task_id, INTAKE_STEP_KEY) is not None


def intake_terminal(task_id: str) -> bool:
    """无 step0 的旧树视为已通过 intake。"""
    st = get_step_status(task_id, INTAKE_STEP_KEY)
    if st is None:
        return True
    return st in {"completed", "skipped", "failed"}


def intake_open(task_id: str) -> bool:
    st = get_step_status(task_id, INTAKE_STEP_KEY)
    return st in {"pending", "running"}


def get_intake_outcome(task_id: str) -> str:
    seed = load_seed(task_id)
    out = str(seed.get("intake_outcome") or "").strip().upper()
    if out in {"A", "B", "C"}:
        return out
    return ""


def is_person_path(task_id: str) -> bool:
    """C：无社交，走人物 web 报告。"""
    return get_intake_outcome(task_id) == "C"


def looks_like_social_in_text(text: str) -> bool:
    t = text or ""
    if re.search(r"https?://[^\s]+", t, re.I):
        if re.search(
            r"(twitter\.com|x\.com|weibo\.com|youtube\.com|youtu\.be|"
            r"instagram\.com|tiktok\.com|t\.me|facebook\.com|fb\.com|"
            r"github\.com|linkedin\.com|bilibili\.com)",
            t,
            re.I,
        ):
            return True
    if re.search(r"@[A-Za-z0-9_\.]{2,}", t):
        return True
    if re.search(
        r"(推特|twitter|微博|weibo|youtube|bilibili|instagram|\bins\b|\big\b|"
        r"tiktok|telegram|\btg\b|facebook|\bfb\b|脸书|github|linkedin)"
        r".{0,40}(@|[A-Za-z0-9_\.]{3,}|https?://)",
        t,
        re.I,
    ):
        return True
    return False


def parse_intake_conclusion(text: str) -> Optional[Dict[str, Any]]:
    """从助手正文解析 [输入分析结论]。

    期望片段示例：
    [输入分析结论]
    outcome: B
    platform: linkedin
    account_handle: amelie-antonio
    person_name: Dr.ª Amélia António
    job_title: President, Casa de Portugal em Macau
    reason: …
    """
    raw = text or ""
    if INTAKE_CONCLUSION_MARKER not in raw:
        return None
    idx = raw.find(INTAKE_CONCLUSION_MARKER)
    body = raw[idx + len(INTAKE_CONCLUSION_MARKER) :]
    # 截到下一标记或文末
    for stop in ("[账号认定结论]", PERSON_ANCHOR_MARKER, "## 一、", "一、基本情况"):
        p = body.find(stop)
        if p >= 0:
            body = body[:p]
    outcome = ""
    m = re.search(r"(?:outcome|分支|结论)\s*[:：]\s*([ABCabc])\b", body)
    if m:
        outcome = m.group(1).upper()
    else:
        m2 = re.search(r"\b([ABC])\s*(?:分支|路径)?\b", body)
        if m2:
            outcome = m2.group(1).upper()
        elif re.search(r"确认无可用社交|无社交(账号|链接)|人物\s*web", body):
            outcome = "C"
        elif re.search(r"搜到了?(可用)?(社交)?链接|回填\s*seed|补全种子", body):
            outcome = "B"
        elif re.search(r"已有社交|输入已含|直接进入主账号", body):
            outcome = "A"
    if outcome not in {"A", "B", "C"}:
        return None

    def _field(*names: str) -> str:
        for name in names:
            mm = re.search(
                rf"(?:{name})\s*[:：]\s*(.+)$",
                body,
                re.I | re.M,
            )
            if mm:
                return mm.group(1).strip().strip("`\"'")
        return ""

    platform = _field("platform", "平台").lower()
    handle = _field("account_handle", "handle", "账号", "username")
    handle = handle.lstrip("@")
    profile_url = _field("profile_url", "url", "链接")
    person_name = _field("person_name", "姓名", "name")
    job_title = _field("job_title", "职位", "title")
    org = _field("org", "机构", "organization")
    reason = _field("reason", "说明", "依据")
    return {
        "outcome": outcome,
        "platform": platform,
        "account_handle": handle,
        "profile_url": profile_url,
        "person_name": person_name,
        "job_title": job_title,
        "org": org,
        "reason": reason,
    }


def _detect_platform_from_url(url: str) -> str:
    u = (url or "").lower()
    mapping = (
        ("linkedin.com", "linkedin"),
        ("twitter.com", "twitter"),
        ("x.com", "twitter"),
        ("weibo.com", "weibo"),
        ("youtube.com", "youtube"),
        ("youtu.be", "youtube"),
        ("instagram.com", "instagram"),
        ("tiktok.com", "tiktok"),
        ("t.me", "telegram"),
        ("facebook.com", "facebook"),
        ("fb.com", "facebook"),
        ("github.com", "github"),
        ("bilibili.com", "bilibili"),
    )
    for needle, plat in mapping:
        if needle in u:
            return plat
    return ""


def apply_intake_outcome(
    store: Any,
    task_id: str,
    parsed: Dict[str, Any],
    *,
    source: str = "agent",
) -> bool:
    """收口 step0，并按 A/B/C 回填 seed / 跳过账号链。"""
    if intake_terminal(task_id) and get_step_status(task_id, INTAKE_STEP_KEY) is not None:
        # 已终态则只允许补写 seed 字段（一般不重入）
        if get_step_status(task_id, INTAKE_STEP_KEY) in {"completed", "skipped"}:
            return False

    outcome = str(parsed.get("outcome") or "").upper()
    if outcome not in {"A", "B", "C"}:
        return False

    seed = load_seed(task_id)
    seed["intake_outcome"] = outcome
    seed["intake_source"] = source
    if parsed.get("person_name"):
        seed["person_name"] = parsed["person_name"]
    if parsed.get("job_title"):
        seed["job_title"] = parsed["job_title"]
    if parsed.get("org"):
        seed["org"] = parsed["org"]
    if parsed.get("reason"):
        seed["intake_reason"] = parsed["reason"]

    if outcome in {"A", "B"}:
        seed["seed_mode"] = "account"
        plat = str(parsed.get("platform") or "").strip().lower()
        handle = str(parsed.get("account_handle") or "").strip().lstrip("@")
        url = str(parsed.get("profile_url") or "").strip()
        detected_platform = _detect_platform_from_url(url) if url else ""
        if url and not detected_platform:
            logger.warning("拒绝非社交主页 URL task=%s url=%s", task_id, url[:120])
            return False
        if plat and detected_platform and plat != detected_platform:
            logger.warning(
                "拒绝平台与 URL 不一致 task=%s platform=%s detected=%s",
                task_id,
                plat,
                detected_platform,
            )
            return False
        if not plat and detected_platform:
            plat = detected_platform
        if plat:
            seed["platform"] = plat
        if handle:
            seed["account_handle"] = handle
            seed["account_hint"] = handle
        if url:
            seed["profile_url"] = url
            if not handle:
                seed["account_hint"] = url[:128]
        effective_platform = str(seed.get("platform") or "").strip().lower()
        effective_handle = str(seed.get("account_handle") or "").strip().lstrip("@")
        effective_url = str(seed.get("profile_url") or "").strip()
        if not effective_platform or not (effective_handle or effective_url):
            logger.warning(
                "拒绝无有效社交种子的 intake=%s task=%s platform=%s handle=%s url=%s",
                outcome,
                task_id,
                effective_platform,
                effective_handle,
                effective_url[:80],
            )
            return False
        if outcome == "B" and not effective_url:
            logger.warning("拒绝没有 profile_url 的 intake=B task=%s", task_id)
            return False
        if outcome == "B" and len(str(parsed.get("reason") or "").strip()) < 20:
            logger.warning("拒绝缺少充分消歧依据的 intake=B task=%s", task_id)
            return False
        seed["parse_status"] = "pending" if outcome == "B" else seed.get("parse_status") or "pending"
    else:
        seed["seed_mode"] = "person"
        seed["parse_status"] = "no_social"

    save_seed(task_id, seed)
    if outcome in {"A", "B"} and str(seed.get("platform") or "").strip():
        platform = str(seed.get("platform") or "").strip().lower()
        db.execute(
            """
            UPDATE collect_phase_steps
            SET title=%s, source_tag=%s, updated_at=NOW(3)
            WHERE task_id=%s AND step_key='step1_seed' AND status IN ('pending','running')
            """,
            (
                seed_agent_title(platform),
                source_tag_json("step1_seed", seed_platform=platform),
                task_id,
            ),
        )

    msg = {
        "A": "输入已含社交账号，进入主账号采集",
        "B": "已搜到可用社交链接并回填种子，进入主账号采集",
        "C": "确认无可用社交链接，跳过账号链，走人物网页报告",
    }.get(outcome, f"intake={outcome}")
    if parsed.get("reason"):
        msg = f"{msg}；{parsed['reason']}"[:240]

    cur = get_step_status(task_id, INTAKE_STEP_KEY)
    if cur not in {"completed", "skipped", "failed"}:
        store.set_step_status(
            task_id,
            INTAKE_STEP_KEY,
            "completed",
            message=msg,
            payload={"outcome": outcome, "source": source},
        )
    # 阶段壳收口
    try:
        ph = get_step_status(task_id, PHASE_INTAKE_SHELL)
        if ph is not None and ph not in {"completed", "skipped", "failed"}:
            store.set_step_status(
                task_id,
                PHASE_INTAKE_SHELL,
                "completed",
                message=f"输入分析完成（{outcome}）",
                skip_phase_rollup=True,
            )
    except Exception as exc:
        logger.warning("收口 phase_intake 失败 task=%s: %s", task_id, exc)

    if outcome == "C":
        _skip_account_chain_for_person(store, task_id)
    return True


def _skip_account_chain_for_person(store: Any, task_id: str) -> None:
    """C 路径：跳过主账号 / Maigret / 候选主页 / 发文。"""
    skips = (
        ("step1_seed", "无社交种子，跳过主账号采集"),
        (MAIGRET_STEP_KEY, "无社交种子，跳过 Maigret"),
        (PROFILE_PARENT_STEP_KEY, "无候选主页，跳过认定佐证采集"),
        (POST_PARENT_STEP_KEY, "无已认定账号，跳过发文采集"),
        ("phase_lock_target", "无社交种子，跳过主账号阶段"),
        ("phase_discovery", "无社交种子，跳过 Maigret 阶段"),
        ("phase_content", "无已认定账号，跳过发文阶段"),
    )
    for key, message in skips:
        st = get_step_status(task_id, key)
        if st is None:
            continue
        if st in {"completed", "skipped", "failed"}:
            continue
        try:
            store.set_step_status(
                task_id,
                key,
                "skipped",
                message=message,
                skip_phase_rollup=True,
            )
        except Exception as exc:
            logger.warning("C路径 skip %s 失败 task=%s: %s", key, task_id, exc)


def try_autocomplete_intake_from_seed(store: Any, task_id: str) -> bool:
    """建任务时已带社交线索 → 直接 A 收口，少绕一圈。"""
    if not has_intake_step(task_id) or intake_terminal(task_id):
        return False
    seed = load_seed(task_id)
    hint_outcome = str(seed.get("intake_outcome") or "").upper()
    handle = str(seed.get("account_handle") or "").strip()
    url = str(seed.get("profile_url") or "").strip()
    has_hint = bool(seed.get("has_social_hint")) or bool(handle) or bool(url)
    if hint_outcome == "A" or (has_hint and hint_outcome in {"", "PENDING", "pending"}):
        return apply_intake_outcome(
            store,
            task_id,
            {
                "outcome": "A",
                "platform": seed.get("platform") or "",
                "account_handle": handle,
                "profile_url": url,
                "person_name": seed.get("person_name") or "",
                "job_title": seed.get("job_title") or "",
                "org": seed.get("org") or "",
                "reason": "输入已含社交账号/链接",
            },
            source="auto_seed",
        )
    return False


def try_apply_intake_from_assistant(store: Any, task_id: str, assistant: str) -> bool:
    if not has_intake_step(task_id) or intake_terminal(task_id):
        return False
    parsed = parse_intake_conclusion(assistant or "")
    if not parsed:
        return False
    return apply_intake_outcome(store, task_id, parsed, source="assistant")


def try_apply_intake_from_thoughts(store: Any, task_id: str) -> bool:
    """思考流已写出 [输入分析结论] 但 step0 未收口时兜底。"""
    if not has_intake_step(task_id) or intake_terminal(task_id):
        return False
    row = db.fetch_one(
        """
        SELECT content FROM hermes_thought_events
        WHERE task_id=%s AND content LIKE %s
        ORDER BY seq DESC
        LIMIT 1
        """,
        (task_id, f"%{INTAKE_CONCLUSION_MARKER}%"),
    )
    content = str((row or {}).get("content") or "")
    if INTAKE_CONCLUSION_MARKER not in content:
        return False
    parsed = parse_intake_conclusion(content)
    if not parsed:
        return False
    ok = apply_intake_outcome(store, task_id, parsed, source="thoughts")
    if ok:
        logger.info("从思考流兜底收口 step0_intake task=%s outcome=%s", task_id, parsed.get("outcome"))
    return bool(ok)


def person_anchor_ready(text: str) -> bool:
    t = text or ""
    return PERSON_ANCHOR_MARKER in t or (
        "[账号认定结论]" in t and bool(re.search(r"无(可用)?社交|未见可靠社交", t))
    )


def bump_osint_budget_for_person(task_id: str) -> Tuple[int, int, int]:
    """返回 (max_search, max_tools, max_wall_sec)；C 路径加大。"""
    if is_person_path(task_id):
        return 12, 18, 600
    return 8, 12, 480
