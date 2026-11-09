"""从用户消息或 Agent 步骤1 输出解析多平台种子账号。

解析优先级：结构化确认块 → 表格 → 宽松键值/口语规则 → 语义邻近配对。
不以单一「平台账号：」字面为唯一入口。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_PLATFORM_ALIASES = {
    "twitter": "twitter",
    "推特": "twitter",
    "x": "twitter",
    "facebook": "facebook",
    "fb": "facebook",
    "脸书": "facebook",
    "youtube": "youtube",
    "油管": "youtube",
    "instagram": "instagram",
    "ins": "instagram",
    "ig": "instagram",
    "telegram": "telegram",
    "tg": "telegram",
    "weibo": "weibo",
    "微博": "weibo",
    "bilibili": "bilibili",
    "b站": "bilibili",
    "哔哩哔哩": "bilibili",
    "tiktok": "tiktok",
    "抖音": "tiktok",
    "github": "github",
    "linkedin": "linkedin",
    "领英": "linkedin",
}

# 平台词（长词优先，避免 x 误伤）；用于规则与语义邻近
_PLATFORM_TOKEN = (
    r"(?:linkedin|领英|twitter|推特|facebook|脸书|youtube|油管|instagram|"
    r"telegram|微博|weibo|bilibili|哔哩哔哩|b站|tiktok|抖音|github|"
    r"\bfb\b|\bins\b|\big\b|\btg\b|\bx\b)"
)

# 用户消息：推特账号：whyyoutouzhele
_MSG_PAIR = re.compile(
    _PLATFORM_TOKEN
    + r"\s*(?:账号|帐户|账户|号|用户|用户名|handle)?\s*[:：\s]\s*@?"
    + r"([A-Za-z0-9_\.\u4e00-\u9fff-]{2,64})",
    re.I,
)

# 口语：推特用户 @elonmusk / 核查推特 @elonmusk / twitter用户elonmusk
_MSG_USER_AT = re.compile(
    _PLATFORM_TOKEN
    + r"\s*(?:平台)?\s*(?:账号|帐户|账户|用户|用户名|handle)?\s*[@＠]?\s*"
    + r"([A-Za-z0-9_\.]{2,64})",
    re.I,
)

# Markdown 表格行：| 1 | 推特 (Twitter/X) | whyyoutouzhele |
_TABLE_ROW = re.compile(
    r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.M,
)

# 列表/键值：平台：twitter（推特） / 用户名：@elonmusk
_KV_PLATFORM = re.compile(
    r"(?:^|\n)\s*[-*]?\s*(?:平台|platform)\s*[:：]\s*([^\n]+)",
    re.I,
)
_KV_HANDLE = re.compile(
    r"(?:^|\n)\s*[-*]?\s*(?:用户名|账号|帐户|账户|handle|user(?:name)?)\s*[:：]\s*@?"
    r"([A-Za-z0-9_\.\u4e00-\u9fff-]{2,64})",
    re.I,
)

# 结构化块（Skill 推荐）
_CONFIRM_BLOCK = re.compile(
    r"\[\s*种子账号确认\s*\](.*?)\[\s*/\s*种子账号确认\s*\]",
    re.I | re.S,
)
# 主页 URL
_URL_TWITTER = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/@?([A-Za-z0-9_]{2,64})",
    re.I,
)
_URL_WEIBO = re.compile(
    r"(?:https?://)?(?:www\.)?weibo\.com/(?:u/)?([A-Za-z0-9_\u4e00-\u9fff]{2,64})",
    re.I,
)
_URL_YT = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/(?:@([A-Za-z0-9_\.]{2,64})|channel/([A-Za-z0-9_\-]{2,64}))",
    re.I,
)
_URL_TG = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]{2,64})",
    re.I,
)
_URL_INS = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_\.]{2,64})",
    re.I,
)
_URL_TT = re.compile(
    r"(?:https?://)?(?:www\.)?tiktok\.com/@([A-Za-z0-9_\.]{2,64})",
    re.I,
)
_URL_GH = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_\-]{2,64})",
    re.I,
)
_URL_LI = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/in/([A-Za-z0-9_\-%]{2,64})",
    re.I,
)

_HANDLE_TOKEN = re.compile(r"[@＠]([A-Za-z0-9_\.]{2,64})")
_PLATFORM_FINDALL = re.compile(_PLATFORM_TOKEN, re.I)

# 语义：确认意图关键词（不要求「步骤1」字面）
_CONFIRM_INTENT = re.compile(
    r"(种子账号|待核查|账号确认|确认种子|账号如下|种子如下|"
    r"接收与确认|本次核查的种子|共\s*\d+\s*个种子|仅此一个平台)",
    re.I,
)

_SKIP_HANDLES = {
    "用户名",
    "handle",
    "username",
    "account",
    "账号",
    "用户名/handle",
}


def _normalize_platform(token: str) -> Optional[str]:
    raw = (token or "").strip().lower()
    raw = raw.replace("（", "(").replace("）", ")")
    if "(" in raw:
        # 优先括号内英文平台名
        inner = raw[raw.find("(") + 1 : raw.rfind(")")] if ")" in raw else ""
        if inner:
            got = _normalize_platform(inner)
            if got:
                return got
        raw = raw.split("(")[0].strip()
    # 长别名优先
    for key in sorted(_PLATFORM_ALIASES.keys(), key=len, reverse=True):
        if key == "x":
            if re.search(r"(?:^|\b)x(?:\b|$)", raw):
                return "twitter"
            continue
        if key in raw:
            return _PLATFORM_ALIASES[key]
    return _PLATFORM_ALIASES.get(raw)


def _normalize_handle(handle: str) -> str:
    h = (handle or "").strip().lstrip("@＠").strip().strip("/")
    # URL 残留 query
    if "?" in h:
        h = h.split("?", 1)[0]
    return h


def _is_bad_handle(handle: str) -> bool:
    h = _normalize_handle(handle)
    if not h or len(h) < 2:
        return True
    if h.lower() in _SKIP_HANDLES:
        return True
    if h in {"平台", "platform", "用户", "账号"}:
        return True
    return False


def _mk(plat: str, handle: str, label: Optional[str] = None) -> Optional[Dict[str, Any]]:
    p = (plat or "").strip()
    h = _normalize_handle(handle)
    if not p or _is_bad_handle(h):
        return None
    item: Dict[str, Any] = {
        "platform": p,
        "account_handle": h,
        "account_id": h,
    }
    if label:
        item["display_label"] = label
    return item


def _dedupe(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in accounts:
        plat = str(item.get("platform") or "").strip()
        handle = _normalize_handle(str(item.get("account_handle") or ""))
        if not plat or _is_bad_handle(handle):
            continue
        key = (plat, handle.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "platform": plat,
                "account_handle": handle,
                "account_id": handle,
                "display_label": item.get("display_label"),
            }
        )
    return out


def parse_from_confirm_block(text: str) -> List[Dict[str, Any]]:
    """解析 [种子账号确认]...[/种子账号确认] 块。"""
    accounts: List[Dict[str, Any]] = []
    line_pat = re.compile(
        r"^(" + _PLATFORM_TOKEN + r")\s*[|｜/,，]\s*@?([A-Za-z0-9_\.]{2,64})\s*$",
        re.I,
    )
    for block in _CONFIRM_BLOCK.finditer(text or ""):
        body = block.group(1) or ""
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = line_pat.match(line)
            if m:
                item = _mk(_normalize_platform(m.group(1)) or "", m.group(2))
                if item:
                    accounts.append(item)
                continue
            # 退化：整行再走口语规则
            accounts.extend(parse_from_user_message(line))
    return _dedupe(accounts)


def parse_from_urls(text: str) -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    t = text or ""
    for m in _URL_TWITTER.finditer(t):
        item = _mk("twitter", m.group(1))
        if item:
            accounts.append(item)
    for m in _URL_WEIBO.finditer(t):
        item = _mk("weibo", m.group(1))
        if item:
            accounts.append(item)
    for m in _URL_YT.finditer(t):
        handle = m.group(1) or m.group(2)
        item = _mk("youtube", handle or "")
        if item:
            accounts.append(item)
    for m in _URL_TG.finditer(t):
        item = _mk("telegram", m.group(1))
        if item:
            accounts.append(item)
    for m in _URL_INS.finditer(t):
        item = _mk("instagram", m.group(1))
        if item:
            accounts.append(item)
    for m in _URL_TT.finditer(t):
        item = _mk("tiktok", m.group(1))
        if item:
            accounts.append(item)
    for m in _URL_GH.finditer(t):
        item = _mk("github", m.group(1))
        if item:
            accounts.append(item)
    for m in _URL_LI.finditer(t):
        item = _mk("linkedin", m.group(1))
        if item:
            accounts.append(item)
    return _dedupe(accounts)


def parse_from_user_message(message: str) -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    text = message or ""
    for m in _MSG_PAIR.finditer(text):
        plat = _normalize_platform(m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0))
        # 上面 pattern 平台是非捕获整体；用 match.group(0) 抽平台 + group(1) handle
        plat = _normalize_platform(m.group(0))
        handle = _normalize_handle(m.group(1))
        item = _mk(plat or "", handle)
        if item:
            accounts.append(item)
    for m in _MSG_USER_AT.finditer(text):
        plat = _normalize_platform(m.group(0))
        handle = _normalize_handle(m.group(1))
        item = _mk(plat or "", handle)
        if item:
            accounts.append(item)
    accounts.extend(parse_from_urls(text))
    return _dedupe(accounts)


def parse_from_assistant_table(text: str) -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    for m in _TABLE_ROW.finditer(text or ""):
        plat_cell = m.group(1).strip()
        handle_cell = m.group(2).strip()
        if "平台" in plat_cell and ("用户" in handle_cell or "handle" in handle_cell.lower()):
            continue
        plat = _normalize_platform(plat_cell)
        handle = _normalize_handle(handle_cell)
        item = _mk(plat or "", handle, label=plat_cell)
        if item:
            accounts.append(item)
    return _dedupe(accounts)


def parse_from_kv_lists(text: str) -> List[Dict[str, Any]]:
    """解析「平台：… / 用户名：…」相邻列表（Agent 常用写法）。"""
    accounts: List[Dict[str, Any]] = []
    lines = (text or "").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        pm = re.search(
            r"(?:平台|platform)\s*[:：]\s*(.+)$",
            line,
            re.I,
        )
        if pm:
            plat = _normalize_platform(pm.group(1))
            # 向后看最多 4 行找用户名
            handle = ""
            for j in range(i + 1, min(i + 5, len(lines))):
                hm = re.search(
                    r"(?:用户名|账号|帐户|账户|handle|user(?:name)?)\s*[:：]\s*@?"
                    r"([A-Za-z0-9_\.\u4e00-\u9fff-]{2,64})",
                    lines[j],
                    re.I,
                )
                if hm:
                    handle = hm.group(1)
                    break
                # 同行已写完则停
                if re.search(r"(?:平台|platform)\s*[:：]", lines[j], re.I):
                    break
            item = _mk(plat or "", handle)
            if item:
                accounts.append(item)
        i += 1
    # 全局 KV 兜底：全文平台列表与用户名列表等长时按序配对
    plats = [_normalize_platform(m.group(1)) for m in _KV_PLATFORM.finditer(text or "")]
    handles = [_normalize_handle(m.group(1)) for m in _KV_HANDLE.finditer(text or "")]
    plats = [p for p in plats if p]
    handles = [h for h in handles if not _is_bad_handle(h)]
    if plats and handles and len(plats) == len(handles):
        for p, h in zip(plats, handles):
            item = _mk(p, h)
            if item:
                accounts.append(item)
    return _dedupe(accounts)


def extract_accounts_semantic(text: str) -> List[Dict[str, Any]]:
    """语义邻近配对：同句/邻行出现平台词与 @handle（或裸 handle）则收。

    不调用外部模型；用「确认意图 + 平台/账号线索邻近」近似语义判断。
    """
    raw = text or ""
    if not raw.strip():
        return []
    accounts: List[Dict[str, Any]] = []
    lines = raw.splitlines()
    for idx, line in enumerate(lines):
        plats_in_line: List[str] = []
        for m in _PLATFORM_FINDALL.finditer(line):
            p = _normalize_platform(m.group(0))
            if p:
                plats_in_line.append(p)
        handles_in_line: List[str] = []
        for m in _HANDLE_TOKEN.finditer(line):
            h = _normalize_handle(m.group(1))
            if not _is_bad_handle(h):
                handles_in_line.append(h)
        # 邻行补 handle / 平台
        window = "\n".join(lines[max(0, idx - 1) : min(len(lines), idx + 3)])
        if not handles_in_line:
            for m in _HANDLE_TOKEN.finditer(window):
                h = _normalize_handle(m.group(1))
                if not _is_bad_handle(h):
                    handles_in_line.append(h)
        if not plats_in_line:
            for m in _PLATFORM_FINDALL.finditer(window):
                p = _normalize_platform(m.group(0))
                if p:
                    plats_in_line.append(p)
        # 去重保序
        plats_in_line = list(dict.fromkeys(plats_in_line))
        handles_in_line = list(dict.fromkeys(handles_in_line))
        if len(plats_in_line) == 1 and handles_in_line:
            for h in handles_in_line:
                item = _mk(plats_in_line[0], h)
                if item:
                    accounts.append(item)
        elif len(plats_in_line) == len(handles_in_line) and plats_in_line:
            for p, h in zip(plats_in_line, handles_in_line):
                item = _mk(p, h)
                if item:
                    accounts.append(item)
    # 全文仅一个平台词 + 一个 @handle
    all_plats = list(
        dict.fromkeys(
            p
            for m in _PLATFORM_FINDALL.finditer(raw)
            for p in [_normalize_platform(m.group(0))]
            if p
        )
    )
    all_handles = list(
        dict.fromkeys(
            h
            for m in _HANDLE_TOKEN.finditer(raw)
            for h in [_normalize_handle(m.group(1))]
            if not _is_bad_handle(h)
        )
    )
    if len(all_plats) == 1 and len(all_handles) == 1:
        item = _mk(all_plats[0], all_handles[0])
        if item:
            accounts.append(item)
    return _dedupe(accounts)


def parse_input_accounts(*, user_message: str = "", assistant_text: str = "") -> List[Dict[str, Any]]:
    """多形态解析：块/表格/键值/口语/URL/语义邻近，结果合并去重。"""
    chunks = [assistant_text or "", user_message or ""]
    merged: List[Dict[str, Any]] = []
    for text in chunks:
        if not (text or "").strip():
            continue
        merged.extend(parse_from_confirm_block(text))
        merged.extend(parse_from_assistant_table(text))
        merged.extend(parse_from_kv_lists(text))
        merged.extend(parse_from_user_message(text))
        # 语义层：有确认意图或已有弱线索时再跑，避免纯噪声正文乱配
        if looks_like_step1_confirmation(text) or merged or "@" in text or "用户" in text:
            merged.extend(extract_accounts_semantic(text))
    return _dedupe(merged)


def looks_like_step1_confirmation(text: str) -> bool:
    """步骤1确认：字面步骤标记，或语义上的种子确认叙述。"""
    t = (text or "").strip()
    if not t:
        return False
    if "步骤1" in t or "步骤一" in t:
        if "种子" in t or "待核查" in t or "确认" in t or "账号" in t:
            return True
    if _CONFIRM_INTENT.search(t):
        return True
    if _CONFIRM_BLOCK.search(t):
        return True
    if "| 平台" in t and "|" in t:
        return True
    if _TABLE_ROW.search(t):
        return True
    # 语义：同时出现平台词 + (@handle 或 用户名：)
    has_plat = bool(_PLATFORM_FINDALL.search(t))
    has_handle = bool(_HANDLE_TOKEN.search(t) or _KV_HANDLE.search(t))
    if has_plat and has_handle and ("种子" in t or "核查" in t or "确认" in t or "账号如下" in t):
        return True
    return False
