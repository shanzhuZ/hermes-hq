# -*- coding: utf-8 -*-
"""04 公开资料核查写报 — hermes-hq 步骤树。

流程（v3 + intake）：
0 输入分析（有社交→A；搜到链接→B；确认无社交→C）→
1 主账号采集 → 2 Maigret 跨平台 → 3 账号认定 →
4 公开信息检索（仅 web_* 备料八章，不搜其它账号）→ 5 全账号发文 → 6 八章报告。
C 路径跳过 1/2/5，步骤3改为人物锚定，步骤4加深 web 备料。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from collect_01.seed_platforms import REPORT_SEED_PROFILE_TOOLS as SEED_PROFILE_TOOLS

PHASE_SEED = "seed"
PHASE_DISCOVERY = "discovery"  # Maigret
PHASE_IDENTITY = "identity"
PHASE_WEB = "web_intel"  # 公开信息检索（模板备料）
PHASE_PROFILES = "profiles"  # 兼容；候选主页挂在认定壳下
PHASE_POSTS = "posts"
PHASE_ANALYSIS = "analysis"  # 兼容旧 phase 名
PHASE_REPORT = "report"
PHASE_DONE = "done"

PHASE_STREAM_VALIDATE = PHASE_IDENTITY
PHASE_VALIDATED = PHASE_IDENTITY

TASK_TYPE = "account_report"
SKILL_NAME = "account-intelligence-report"

STEP_PLAN_KEY = "step_plan"

PHASE_INTAKE_SHELL = "phase_intake"
PHASE_LOCK_TARGET = "phase_lock_target"
PHASE_DISCOVERY_SHELL = "phase_discovery"
PHASE_IDENTITY_SHELL = "phase_identity"
PHASE_WEB_SHELL = "phase_web_intel"
# 兼容旧壳名（不再进树）
PHASE_ACCOUNT_COLLECT = "phase_account_collect"
PHASE_ANALYSIS_SHELL = "phase_analysis"
PHASE_CONTENT = "phase_content"
PHASE_REPORT_SHELL = "phase_report"
PHASE_COLLISION = PHASE_IDENTITY_SHELL

_MCP_SEED_PLATFORMS = frozenset({"twitter", "weibo", "youtube", "bilibili"})

ANALYSIS_STEP_KEYS: Tuple[str, ...] = ()

INTAKE_STEP_KEY = "step0_intake"
MAIGRET_STEP_KEY = "step2_maigret"
IDENTITY_STEP_KEY = "step3_identity"
# 兼容旧代码里的 step4_identity 字面量：门禁可用 resolve
IDENTITY_STEP_KEYS = (IDENTITY_STEP_KEY, "step4_identity")
OSINT_WEB_STEP_KEY = "step4_osint_web"
# 兼容旧字面量
OSINT_WEB_STEP_KEYS = (OSINT_WEB_STEP_KEY, "step2_osint_web")
# 认定阶段可采 Maigret 候选主页（非种子重复采）；父节点挂在认定壳下
PROFILE_PARENT_STEP_KEY = "step3_profiles"
POST_PARENT_STEP_KEY = "step5_posts"
REPORT_STEP_KEY = "step7_report"

# 旧树文本流/图片流兼容键必须与 v3 的 step3_identity 物理隔离。
# 过去三者都别名到 step3_identity，后台图片线程会把真实认定结论覆写成 skipped。
STREAM_PARENT_STEP_KEY = "step4_identity"
STREAM_TEXT_STEP_KEY = "step4_text_compare"
STREAM_IMAGE_STEP_KEY = "step4_image_compare"
STREAM_TEXT_CONCLUSION_MARKER = "[账号认定结论]"
PERSON_ANCHOR_CONCLUSION_MARKER = "[人物锚定结论]"
INTAKE_CONCLUSION_MARKER = "[输入分析结论]"
OSINT_ES_STEP_KEY = "step6_osint_es"
OSINT_CONCLUSION_MARKER = "[社工库核验结论]"
PDL_STEP_KEY = "step6_pdl"
STEP6_GEO_VERIFY = "step6_geo_verify"
STEP6_RELATION_GRAPH = "step6_relation_graph"
STEP6_RUMOR_SX = "step6_rumor_sx"
COLLISION_DEMO_STEP_KEYS = frozenset()


@dataclass(frozen=True)
class StepDef:
    step_key: str
    title: str
    step_order: int
    step_node: str
    parent_step_key: Optional[str] = None
    current_phase: Optional[str] = None


PLATFORM_LABELS: Dict[str, str] = {
    "twitter": "Twitter",
    "youtube": "YouTube",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "telegram": "Telegram",
    "weibo": "微博",
    "bilibili": "B站",
    "facebook": "Facebook",
    "github": "GitHub",
    "reddit": "Reddit",
    "linkedin": "LinkedIn",
    "vk": "VK",
}

PLATFORM_STEP_INDEX: Dict[str, int] = {
    "twitter": 1,
    "facebook": 2,
    "youtube": 3,
    "instagram": 4,
    "telegram": 5,
    "weibo": 6,
    "tiktok": 7,
    "github": 8,
    "reddit": 9,
    "linkedin": 10,
    "vk": 11,
    "bilibili": 12,
}


def seed_agent_title(platform: Optional[str]) -> str:
    plat = (platform or "twitter").lower().strip()
    label = PLATFORM_LABELS.get(plat, plat)
    if plat in _MCP_SEED_PLATFORMS:
        return f"{label} MCP Agent 采集"
    return f"Apify Agent · {label} 采集"


def phase_shell_steps() -> Tuple[StepDef, ...]:
    """L1 阶段壳：intake + 六大业务阶段。"""
    return (
        StepDef(PHASE_INTAKE_SHELL, "0. 输入分析", 50, "0", STEP_PLAN_KEY, PHASE_SEED),
        StepDef(PHASE_LOCK_TARGET, "1. 主账号采集", 100, "1", STEP_PLAN_KEY, PHASE_SEED),
        StepDef(PHASE_DISCOVERY_SHELL, "2. Maigret 跨平台检索", 200, "2", STEP_PLAN_KEY, PHASE_DISCOVERY),
        StepDef(PHASE_IDENTITY_SHELL, "3. 账号认定", 300, "3", STEP_PLAN_KEY, PHASE_IDENTITY),
        StepDef(PHASE_WEB_SHELL, "4. 公开信息检索", 400, "4", STEP_PLAN_KEY, PHASE_WEB),
        StepDef(PHASE_CONTENT, "5. 全账号发文采集", 500, "5", STEP_PLAN_KEY, PHASE_POSTS),
        StepDef(PHASE_REPORT_SHELL, "6. 报告生成", 600, "6", STEP_PLAN_KEY, PHASE_REPORT),
    )


def execution_steps_for_platform(platform: Optional[str] = None) -> Tuple[StepDef, ...]:
    """业务执行步。"""
    return (
        StepDef(
            INTAKE_STEP_KEY,
            "输入分析 Agent（分流 A/B/C）",
            55,
            "0.1",
            PHASE_INTAKE_SHELL,
            PHASE_SEED,
        ),
        StepDef("step1_seed", seed_agent_title(platform), 110, "1.1", PHASE_LOCK_TARGET, PHASE_SEED),
        StepDef(
            MAIGRET_STEP_KEY,
            "Maigret Agent 跨平台账号检索",
            210,
            "2.1",
            PHASE_DISCOVERY_SHELL,
            PHASE_DISCOVERY,
        ),
        StepDef(
            IDENTITY_STEP_KEY,
            "账号认定 Agent",
            310,
            "3.1",
            PHASE_IDENTITY_SHELL,
            PHASE_IDENTITY,
        ),
        StepDef(
            PROFILE_PARENT_STEP_KEY,
            "候选主页采集（可选认定佐证）",
            320,
            "3.2",
            PHASE_IDENTITY_SHELL,
            PHASE_IDENTITY,
        ),
        StepDef(
            OSINT_WEB_STEP_KEY,
            "网页检索 Agent 公开信息备料",
            410,
            "4.1",
            PHASE_WEB_SHELL,
            PHASE_WEB,
        ),
        StepDef(
            POST_PARENT_STEP_KEY,
            "跨平台发文与公开表达采集 Agent",
            510,
            "5.1",
            PHASE_CONTENT,
            PHASE_POSTS,
        ),
        StepDef(
            REPORT_STEP_KEY,
            "公开资料核查报告 Agent",
            610,
            "6.1",
            PHASE_REPORT_SHELL,
            PHASE_REPORT,
        ),
    )


def root_steps_for_platform(platform: Optional[str] = None) -> Tuple[StepDef, ...]:
    plan = StepDef(STEP_PLAN_KEY, "制定执行计划", 5, "P", None, None)
    return (plan,) + phase_shell_steps() + execution_steps_for_platform(platform)


ROOT_STEPS: Tuple[StepDef, ...] = root_steps_for_platform("twitter")

MAIGRET_TOOLS = frozenset(
    {
        "mcp_maigret_collect_accounts",
        "mcp_maigret_ai_investigation",
        "mcp_maigret_cross_platform_analysis",
        "mcp_maigret_extract_profile_info",
        "mcp_maigret_parse_profile_url",
        "mcp_maigret_generate_report",
        "mcp_maigret_database_stats",
    }
)

TOOL_PRIMARY_STEP: Dict[str, str] = {
    "mcp_twitter_get_user_info": "step1_seed",
    "mcp_youtube_get_channel_stats": "step1_seed",
    "mcp_weibo_get_profile": "step1_seed",
    "mcp_bilibili_get_user_info": "step1_seed",
    "mcp_maigret_collect_accounts": MAIGRET_STEP_KEY,
    "mcp_maigret_ai_investigation": MAIGRET_STEP_KEY,
    "mcp_maigret_cross_platform_analysis": MAIGRET_STEP_KEY,
    "mcp_maigret_extract_profile_info": MAIGRET_STEP_KEY,
    "mcp_maigret_parse_profile_url": MAIGRET_STEP_KEY,
    "mcp_maigret_generate_report": MAIGRET_STEP_KEY,
    "mcp_maigret_database_stats": MAIGRET_STEP_KEY,
    "web_search": OSINT_WEB_STEP_KEY,
    "web_extract": OSINT_WEB_STEP_KEY,
    "browser_navigate": OSINT_WEB_STEP_KEY,
    "browser_vision": OSINT_WEB_STEP_KEY,
    "browser_click": OSINT_WEB_STEP_KEY,
    "browser_type": OSINT_WEB_STEP_KEY,
    "mcp_apify_apify__instagram_scraper": PROFILE_PARENT_STEP_KEY,
    "mcp_apify_clockworks__tiktok_scraper": PROFILE_PARENT_STEP_KEY,
    "mcp_apify_vujeen__telegram_channel_scraper": PROFILE_PARENT_STEP_KEY,
    "mcp_apify_headlessagent__facebook_profile_post_scraper": PROFILE_PARENT_STEP_KEY,
    "mcp_apify_knotless_cadence__github_profile_scraper": PROFILE_PARENT_STEP_KEY,
    "mcp_apify_harvestapi__linkedin_profile_scraper": PROFILE_PARENT_STEP_KEY,
    "mcp_apify_get_dataset_items": PROFILE_PARENT_STEP_KEY,
    "mcp_apify_get_actor_run": PROFILE_PARENT_STEP_KEY,
    "mcp_twitter_get_user_tweets": POST_PARENT_STEP_KEY,
    "mcp_youtube_analyze_channel_videos": POST_PARENT_STEP_KEY,
    "mcp_weibo_get_user_feeds": POST_PARENT_STEP_KEY,
    "mcp_weibo_get_feeds": POST_PARENT_STEP_KEY,
    "mcp_apify_harvestapi__linkedin_profile_posts": POST_PARENT_STEP_KEY,
}

PROFILE_TOOLS = frozenset(
    {
        "mcp_twitter_get_user_info",
        "mcp_youtube_get_channel_stats",
        "mcp_weibo_get_profile",
        "mcp_bilibili_get_user_info",
        "mcp_apify_apify__instagram_scraper",
        "mcp_apify_clockworks__tiktok_scraper",
        "mcp_apify_vujeen__telegram_channel_scraper",
        "mcp_apify_headlessagent__facebook_profile_post_scraper",
        "mcp_apify_knotless_cadence__github_profile_scraper",
        "mcp_apify_harvestapi__linkedin_profile_scraper",
        "mcp_apify_get_actor_run",
    }
)

POST_TOOLS = frozenset(
    {
        "mcp_twitter_get_user_tweets",
        "mcp_youtube_analyze_channel_videos",
        "mcp_weibo_get_user_feeds",
        "mcp_weibo_get_feeds",
        "mcp_apify_get_dataset_items",
    }
)

STEP5_STREAM_TOOLS = frozenset()
STEP8_VISION_TOOLS = frozenset({"mcp_vision_analyze", "vision_analyze", "mcp_ocr_perform_ocr"})

WEB_SEARCH_TOOLS = frozenset(
    {
        "web_search",
        "web_extract",
        "browser_navigate",
        "browser_vision",
        "browser_click",
        "browser_type",
    }
)

APIFY_POST_TOOLS = {
    "mcp_apify_apify__instagram_scraper",
    "mcp_apify_clockworks__tiktok_scraper",
    "mcp_apify_vujeen__telegram_channel_scraper",
    "mcp_apify_headlessagent__facebook_profile_post_scraper",
    "mcp_apify_knotless_cadence__github_profile_scraper",
    "mcp_apify_harvestapi__linkedin_profile_posts",
}

STEP4_COLLECT_TOOLS = PROFILE_TOOLS | POST_TOOLS | APIFY_POST_TOOLS | frozenset(
    {"mcp_apify_get_actor_run", "mcp_apify_get_dataset_items"}
)

APIFY_TOOL_PLATFORM: Dict[str, str] = {
    "mcp_apify_apify__instagram_scraper": "instagram",
    "mcp_apify_clockworks__tiktok_scraper": "tiktok",
    "mcp_apify_vujeen__telegram_channel_scraper": "telegram",
    "mcp_apify_headlessagent__facebook_profile_post_scraper": "facebook",
    "mcp_apify_knotless_cadence__github_profile_scraper": "github",
    "mcp_apify_harvestapi__linkedin_profile_scraper": "linkedin",
}

TOOL_PLATFORM: Dict[str, str] = {
    "mcp_twitter_get_user_info": "twitter",
    "mcp_twitter_get_user_tweets": "twitter",
    "mcp_youtube_get_channel_stats": "youtube",
    "mcp_youtube_analyze_channel_videos": "youtube",
    "mcp_weibo_get_profile": "weibo",
    "mcp_weibo_get_user_feeds": "weibo",
    "mcp_weibo_get_feeds": "weibo",
    "mcp_bilibili_get_user_info": "bilibili",
    **APIFY_TOOL_PLATFORM,
    "mcp_apify_harvestapi__linkedin_profile_posts": "linkedin",
}

TOOL_POST_PLATFORM: Dict[str, str] = {
    "mcp_twitter_get_user_tweets": "twitter",
    "mcp_youtube_analyze_channel_videos": "youtube",
    "mcp_weibo_get_user_feeds": "weibo",
    "mcp_weibo_get_feeds": "weibo",
    "mcp_apify_harvestapi__linkedin_profile_posts": "linkedin",
}

NON_COLLECTIBLE_PLATFORMS = frozenset(
    {
        "imginn",
        "picuki",
        "googlescholar",
        "blogger",
        "discord",
        "snapchat",
        "steam",
        "wordpress",
        "opggloltaiwan",
        "naver",
        "slack",
        "twitch",
        "vk",
        "reddit",
        "pinterest",
        "medium",
        "tumblr",
    }
)

_COLLECTIBLE_PLATFORM_SET = frozenset(set(TOOL_PLATFORM.values()) | set(APIFY_TOOL_PLATFORM.values()))


def is_collectible_platform(platform: str) -> bool:
    p = (platform or "").strip().lower()
    if not p or p in NON_COLLECTIBLE_PLATFORMS:
        return False
    return p in _COLLECTIBLE_PLATFORM_SET


def profile_platform_step_key(platform: str) -> str:
    return f"step3_profile_{platform}"


def post_platform_step_key(platform: str) -> str:
    return f"step5_post_{platform}"


def profile_step_title(platform: str, handle: str = "") -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    if handle:
        return f"{label} Agent 主页采集 · @{handle.lstrip('@')}"
    return f"{label} Agent 主页采集"


def post_step_title(platform: str, handle: str = "") -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    if handle:
        return f"{label} Agent 发文采集 · @{handle.lstrip('@')}"
    return f"{label} Agent 发文采集"


def profile_step_order(platform: str) -> int:
    return 320 + PLATFORM_STEP_INDEX.get(platform, 90)


def post_step_order(platform: str) -> int:
    return 510 + PLATFORM_STEP_INDEX.get(platform, 90)


def profile_step_node(platform: str) -> str:
    idx = PLATFORM_STEP_INDEX.get(platform, 90)
    return f"3.2.{idx}"


def post_step_node(platform: str) -> str:
    idx = PLATFORM_STEP_INDEX.get(platform, 90)
    return f"5.1.{idx}"


def video_step_key(platform: str) -> str:
    return f"step5_video_{platform}"


def video_step_title(platform: str) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    return f"{label}视频分析"


def video_step_order(platform: str) -> int:
    return post_step_order(platform) + 1


def video_step_node(platform: str) -> str:
    return f"{post_step_node(platform)}.1"


def is_profile_platform_step(step_key: Optional[str]) -> bool:
    sk = str(step_key or "")
    return sk.startswith("step3_profile_") or sk.startswith("step4_profile_")


def is_post_platform_step(step_key: Optional[str]) -> bool:
    sk = str(step_key or "")
    return sk.startswith("step5_post_") or sk.startswith("step7_post_")


def is_video_platform_step(step_key: Optional[str]) -> bool:
    sk = str(step_key or "")
    return sk.startswith("step5_video_") or sk.startswith("step7_video_")


def tool_collect_step_key(tool_name: str, platform: Optional[str]) -> str:
    if not platform:
        return TOOL_PRIMARY_STEP.get(tool_name, PROFILE_PARENT_STEP_KEY)
    if tool_name in POST_TOOLS:
        return post_platform_step_key(platform)
    if tool_name in PROFILE_TOOLS:
        return profile_platform_step_key(platform)
    return profile_platform_step_key(platform)


def root_step_keys() -> List[str]:
    return [s.step_key for s in execution_steps_for_platform("twitter")]


def is_collision_demo_step(step_key: Optional[str]) -> bool:
    return False


def initial_steps(platform: Optional[str] = None) -> List[StepDef]:
    return list(root_steps_for_platform(platform))


def tool_step_key(tool_name: str) -> str:
    return TOOL_PRIMARY_STEP.get(tool_name, PROFILE_PARENT_STEP_KEY)


PHASE_SHELL_KEYS = frozenset(s.step_key for s in phase_shell_steps())

EXECUTION_PARENT_SHELL: Dict[str, str] = {
    s.step_key: str(s.parent_step_key)
    for s in execution_steps_for_platform("twitter")
    if s.parent_step_key
}


def is_phase_shell(step_key: Optional[str]) -> bool:
    return bool(step_key) and str(step_key) in PHASE_SHELL_KEYS


def phase_shell_of_execution_step(step_key: Optional[str]) -> Optional[str]:
    if not step_key:
        return None
    return EXECUTION_PARENT_SHELL.get(str(step_key))


def immediate_parent_step_key(step_key: Optional[str]) -> Optional[str]:
    if not step_key:
        return None
    sk = str(step_key)
    if is_video_platform_step(sk):
        plat = sk.replace("step5_video_", "").replace("step7_video_", "")
        return post_platform_step_key(plat)
    if is_post_platform_step(sk):
        return POST_PARENT_STEP_KEY
    if is_profile_platform_step(sk):
        return PROFILE_PARENT_STEP_KEY
    return EXECUTION_PARENT_SHELL.get(sk)


def direct_execution_children(phase_key: str) -> List[str]:
    return [k for k, p in EXECUTION_PARENT_SHELL.items() if p == phase_key]


def step_phase(step_key: str) -> Optional[str]:
    for s in ROOT_STEPS:
        if s.step_key == step_key:
            return s.current_phase
    if is_profile_platform_step(step_key):
        return PHASE_IDENTITY
    if is_post_platform_step(step_key) or is_video_platform_step(step_key):
        return PHASE_POSTS
    if step_key in OSINT_WEB_STEP_KEYS:
        return PHASE_WEB
    if step_key == MAIGRET_STEP_KEY or str(step_key).startswith("mcp_maigret"):
        return PHASE_DISCOVERY
    return None
