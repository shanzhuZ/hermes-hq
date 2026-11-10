"""写报 assistant 文本解析：跳步、分析步骤、终稿。"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from report_04.phases import ANALYSIS_STEP_KEYS

_PROGRESS_PATTERNS = (
    re.compile(r"现在.*步骤\s*[89]|并行执行步骤\s*[89]", re.I),
    re.compile(r"一次性输出.*报告", re.I),
    re.compile(r"准备.*步骤\s*[89]", re.I),
)

_SKIP_STEP2 = re.compile(r"跳过步骤\s*2|不跨平台|单平台", re.I)
_SKIP_STEP34 = re.compile(r"跳过步骤\s*3|跳过步骤\s*3-4|跳过步骤\s*3、4", re.I)

_STEP_BLOCK = re.compile(
    r"步骤\s*(8|9|10)\s*[：:]\s*([\s\S]*?)(?=步骤\s*(?:8|9|10|11)\s*[：:]|$)",
    re.I,
)

_FINAL_MARKERS = (
    "一、基本情况",
    "二、在职在岗情况",
    "三、人脉资源",
    "四、政治立场",
    "五、污点劣迹",
    "六、公开表达与专业关注点",
    "七、身份核验与综合结论",
    "八、主要来源",
    # 兼容旧六章终稿（历史任务）
    "一、账号基本信息",
    "二、账号全网关联账号",
    "六、综合研判与核查情况",
)

_SECTION5_HEAD = "五、污点劣迹"
_SECTION6_HEAD = "六、公开表达与专业关注点"

_SECTION1_HEAD = "一、基本情况"

# 终稿末尾主题标签块（落库时剥掉，写入 hermes_user_dialogues.report_tags）
_REPORT_TAGS_BLOCK = re.compile(
    r"\[报告标签\]\s*([\s\S]*?)\s*\[/报告标签\]\s*",
    re.I,
)
# 容错：模型常漏写闭标签，仅接受「开标签到文末」且中间不含其它 [
_REPORT_TAGS_OPEN_ONLY = re.compile(
    r"\[报告标签\]\s*([^\[\]]*?)\s*\Z",
    re.I,
)

# 终稿正文禁止出现的管线/运维脏数据（命中则不算合法终稿，也不做 8～10 回填）
_DIRTY_META_PATTERNS = (
    re.compile(r"步骤\s*7\.5", re.I),
    re.compile(r"步骤\s*3\.5", re.I),
    re.compile(r"图片资产管线|图片管线", re.I),
    re.compile(r"image_pipeline", re.I),
    re.compile(r"force-?analyze", re.I),
    re.compile(r"ModuleNotFoundError|PYTHONPATH|db_sink", re.I),
    re.compile(r"未部署|未注册|跳过步骤\s*7\.5|跳过步骤\s*3\.5", re.I),
    re.compile(r"\btask_id\b|任务\s*ID\s*[：:]", re.I),
    re.compile(r"collect_images|skip_if_stored|HERMES_REPORT_", re.I),
    re.compile(r"shell\s+hook|Hook\s*超时|120s", re.I),
    re.compile(r"管线未找到|即席执行|非\s*Gateway\s*会话", re.I),
)


def has_named_report_header(content: str) -> bool:
    """首行须包含具体姓名和「公开资料核查报告」，不能只有通用标题。"""
    raw = (content or "").lstrip()
    if not raw:
        return False
    first = raw.splitlines()[0].strip().lstrip("#").strip()
    marker = "公开资料核查报告"
    if marker not in first:
        return False
    subject = first.split(marker, 1)[0].strip(" ：:-—")
    return bool(subject and subject not in {"姓名", "{姓名}", "XXXX", "XXX"})


def report_header_photo_valid(content: str) -> bool:
    """本人照片可选；有图须为 HTTP(S) Markdown 图片并带来源，无图须省略照片字段。"""
    raw = content or ""
    section_idx = raw.find(_SECTION1_HEAD)
    header = raw if section_idx < 0 else raw[:section_idx]
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", header)
    if images:
        if any(not re.match(r"^https?://", url.strip(), re.I) for url in images):
            return False
        return "照片来源" in header
    return not bool(re.search(r"照片来源|暂无照片|无照片|照片\s*[：:]", header))


def strip_invalid_header_photo(content: str) -> str:
    """非法/占位照片字段从文首剥掉，避免小格式问题导致整篇终稿打回。"""
    raw = content or ""
    if not raw:
        return ""
    if report_header_photo_valid(raw):
        return raw
    section_idx = raw.find(_SECTION1_HEAD)
    if section_idx < 0:
        header, rest = raw, ""
    else:
        header, rest = raw[:section_idx], raw[section_idx:]
    kept: List[str] = []
    for line in header.splitlines():
        if re.search(r"!\[[^\]]*\]\([^)]+\)", line):
            continue
        if re.search(r"照片来源|暂无照片|无照片|照片\s*[：:]", line):
            continue
        kept.append(line)
    header2 = "\n".join(kept).strip()
    if rest:
        return (header2 + "\n\n" + rest).strip() if header2 else rest.strip()
    return header2


def extract_report_body(content: str) -> str:
    """剥掉终稿前的进度元叙述，从「一、基本情况」（或旧「一、账号基本信息」）起截取。"""
    raw = (content or "").strip()
    if not raw:
        return ""
    # 新模板的姓名/原名/图片属于终稿正文，禁止像旧进度前缀一样裁掉。
    if has_named_report_header(raw):
        return raw
    markers = (
        "## 一、基本情况",
        "# 一、基本情况",
        "一、基本情况",
        "## 一、账号基本信息",
        "# 一、账号基本信息",
        "一、账号基本信息",
        "公开资料核查报告",
    )
    best = -1
    for m in markers:
        i = raw.find(m)
        if i >= 0 and (best < 0 or i < best):
            best = i
    if best < 0:
        return raw
    return raw[best:].strip()


def is_progress_only(text: str) -> bool:
    """进度播报，不应完成分析步骤。"""
    t = (text or "").strip()
    for pat in _PROGRESS_PATTERNS:
        if pat.search(t):
            return True
    return False


def detect_skip_steps(text: str) -> List[str]:
    """单平台路径：返回应 skipped 的根步骤 key。"""
    if not text:
        return []
    skipped: List[str] = []
    if _SKIP_STEP2.search(text):
        # hq：无 Maigret；单平台时可跳过网页扩线索，仍须采主页
        skipped.extend([])
    elif _SKIP_STEP34.search(text):
        skipped.extend(["step2_osint_web"])
    return skipped


def has_report_dirty_meta(content: str) -> bool:
    """终稿是否夹带管线/运维元叙述。"""
    t = content or ""
    return any(p.search(t) for p in _DIRTY_META_PATTERNS)


def sanitize_report_dirty_meta(content: str) -> str:
    """删除命中管线脏词的整行，保留业务章节；不关脏门禁，只做可落库清洗。"""
    raw = content or ""
    if not raw.strip():
        return ""
    if not has_report_dirty_meta(raw):
        return raw.strip()
    kept: List[str] = []
    for line in raw.splitlines():
        if any(p.search(line) for p in _DIRTY_META_PATTERNS):
            continue
        kept.append(line)
    text = "\n".join(kept)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def prepare_final_report_body(content: str) -> str:
    """剥前缀进度句 + 清洗管线脏行，得到可判定/回填用的终稿正文。

    注意：不剥 [报告标签] 块。标签须保留到 save_assistant_output，由 extract_report_tags 落库；
    若在此剥掉，调用方把返回值再当 assistant 传入时 tags 会永久丢失。
    """
    return sanitize_report_dirty_meta(extract_report_body(content))


_CHAPTER_LINE_RE = re.compile(
    r"^(#{1,6}\s*)?([一二三四五六七八]、[^\n]+)\s*$",
    re.M,
)
_SUBSECTION_LINE_RE = re.compile(
    r"^(#{1,6}\s*)?(（[一二三四五六七八九十]+）[^\n]+)\s*$",
    re.M,
)
_SECTION7_LABELS = ("身份核验", "账号认定", "综合结论")
_SECTION7_SPLIT_RE = re.compile(
    r"(?=身份核验\s*[：:]|账号认定\s*[：:]|综合结论\s*[：:])"
)
_SECTION7_ITEM_RE = re.compile(
    r"^(身份核验|账号认定|综合结论)\s*[：:]\s*([\s\S]*)$"
)
_ORDERED_ITEM_RE = re.compile(r"^\s*\d+[\.、]\s+")
_BULLET_ITEM_RE = re.compile(r"^\s*[-*•]\s+")


def _promote_heading_levels(text: str) -> str:
    """一～八章升为 ##，（一）（二）升为 ###，便于前端 Markdown 放大加粗。"""

    def _chapter(m: re.Match) -> str:
        return "## " + m.group(2).strip()

    def _sub(m: re.Match) -> str:
        return "### " + m.group(2).strip()

    out = _CHAPTER_LINE_RE.sub(_chapter, text or "")
    out = _SUBSECTION_LINE_RE.sub(_sub, out)
    return out


def _format_section7_body(body: str) -> str:
    """第七章：把「身份核验/账号认定/综合结论」拆成 1. 2. 3. 列表。"""
    raw = (body or "").strip()
    if not raw:
        return raw
    # 已是规范序号且含标签，不强制重排
    if _ORDERED_ITEM_RE.search(raw) and all(x in raw for x in _SECTION7_LABELS):
        return raw
    parts = [p.strip() for p in _SECTION7_SPLIT_RE.split(raw) if p and p.strip()]
    items: List[str] = []
    for part in parts:
        m = _SECTION7_ITEM_RE.match(part)
        if m:
            label, content = m.group(1), (m.group(2) or "").strip()
            content = re.sub(r"\s+", " ", content).strip(" ；;。")
            if content:
                items.append(f"{len(items) + 1}. **{label}**：{content}")
            else:
                items.append(f"{len(items) + 1}. **{label}**：未核实")
        elif part:
            # 无标签的残留段：并入列表末项或作为补充点
            chunk = re.sub(r"\s+", " ", part).strip()
            if chunk:
                items.append(f"{len(items) + 1}. {chunk}")
    if len(items) >= 2:
        return "\n".join(items)
    # 整段无标签：按句号粗拆（至少 2 句才拆）
    sentences = [s.strip() for s in re.split(r"(?<=[。！？])\s*", raw) if s.strip()]
    if len(sentences) >= 2:
        return "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1))
    return raw


def _format_section8_body(body: str) -> str:
    """第八章：来源统一为 1. 2. 3. 有序列表。"""
    raw = (body or "").strip()
    if not raw:
        return raw
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    items: List[str] = []
    for ln in lines:
        ln = _ORDERED_ITEM_RE.sub("", ln)
        ln = _BULLET_ITEM_RE.sub("", ln)
        ln = ln.strip()
        if ln:
            items.append(f"{len(items) + 1}. {ln}")
    return "\n".join(items) if items else raw


def _replace_section_body(text: str, section_head: str, next_heads: tuple, formatter) -> str:
    """替换某一章标题后、下一章标题前的正文。"""
    raw = text or ""
    # 允许已有 ## 前缀
    pat = re.compile(
        rf"(^|\n)(#{{1,6}}\s*)?({re.escape(section_head)})\s*\n",
        re.M,
    )
    m = pat.search(raw)
    if not m:
        return raw
    start = m.end()
    end = len(raw)
    for nh in next_heads:
        npat = re.compile(
            rf"(^|\n)(#{{1,6}}\s*)?({re.escape(nh)})\s*(\n|$)",
            re.M,
        )
        nm = npat.search(raw, start)
        if nm:
            end = nm.start()
            break
    old_body = raw[start:end]
    new_body = formatter(old_body)
    if new_body.strip() == old_body.strip():
        return raw
    # 保留章节后空行观感
    return raw[:start] + new_body.strip() + "\n" + raw[end:].lstrip("\n")


def format_report_markdown_hierarchy(content: str) -> str:
    """终稿展示格式：章标题 ##、小节 ###、七/八章正文序号化。

    不改变章节名称与验收关键字，仅调整 Markdown 层级与列表形态。
    """
    text = (content or "").strip()
    if not text:
        return text
    text = _promote_heading_levels(text)
    text = _replace_section_body(
        text,
        "七、身份核验与综合结论",
        ("八、主要来源",),
        _format_section7_body,
    )
    text = _replace_section_body(
        text,
        "八、主要来源",
        ("[报告标签]",),
        _format_section8_body,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _parse_report_tag_chunk(chunk: str) -> List[str]:
    """把标签块正文拆成去重列表（最多 12 项，单项 ≤32 字）。"""
    tags: List[str] = []
    seen: Set[str] = set()
    for part in re.split(r"[,，、\n;；]+", (chunk or "").strip()):
        t = part.strip()
        if not t or len(t) > 32:
            continue
        if t in seen:
            continue
        seen.add(t)
        tags.append(t)
        if len(tags) >= 12:
            break
    return tags


def extract_report_tags(content: str) -> Tuple[str, List[str]]:
    """剥掉 [报告标签]...[/报告标签]，返回 (正文, 去重后的标签列表)。

    标签按逗号/顿号/换行拆分。优先成对匹配；若漏写闭标签但开标签在文末，同样剥掉并解析。
    """
    raw = (content or "").strip()
    if not raw:
        return "", []
    m = _REPORT_TAGS_BLOCK.search(raw)
    if not m:
        m = _REPORT_TAGS_OPEN_ONLY.search(raw)
    if not m:
        return raw, []
    body = (raw[: m.start()] + raw[m.end() :]).strip()
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    tags = _parse_report_tag_chunk(m.group(1) or "")
    return body, tags


def starts_with_report_section1(content: str) -> bool:
    """终稿须以报告标题、「一、基本情况」或旧「一、账号基本信息」起笔。"""
    t = (content or "").lstrip()
    if not t:
        return False
    if t.startswith("##"):
        t = t[2:].lstrip()
    elif t.startswith("#"):
        t = t[1:].lstrip()
    if has_named_report_header(t):
        return True
    return t.startswith(_SECTION1_HEAD) or t.startswith("一、账号基本信息")


def _section_marker_hits(body: str) -> int:
    text = (body or "").replace(" ", "").replace("\u3000", "")
    return sum(1 for m in _FINAL_MARKERS if m in text)


def looks_like_report_attempt(content: str) -> bool:
    """不论是否脏：是否像在写四章终稿（用于 fail-forward，防 8～10 永久 running）。"""
    body = extract_report_body(content)
    if len(body) < 200:
        return False
    if not starts_with_report_section1(body):
        return False
    return _section_marker_hits(body) >= 2


def follows_current_report_template(content: str) -> bool:
    """新八章模板：固定章节与 DOCX 规定的二级项不可省略（严格版，供校验/测试）。"""
    compact = (content or "").replace(" ", "").replace("\u3000", "")
    required_heads = (
        "一、基本情况",
        "二、在职在岗情况",
        "三、人脉资源",
        "四、政治立场",
        "五、污点劣迹",
        "六、公开表达与专业关注点",
        "七、身份核验与综合结论",
        "八、主要来源",
    )
    if any(head not in compact for head in required_heads):
        return False

    section1 = _extract_section(content, "一、基本情况", ("二、在职在岗情况",))
    section2 = _extract_section(content, "二、在职在岗情况", ("三、人脉资源",))
    section4 = _extract_section(content, "四、政治立场", ("五、污点劣迹",))
    section5 = _extract_section(content, "五、污点劣迹", ("六、公开表达与专业关注点",))

    required_section1 = (
        "社交媒体",
        "（一）教育经历",
        "（二）工作经历",
        "（三）性格特点",
        "（四）家庭成员情况",
        "（五）经济状况",
    )
    required_section2 = (
        "（一）工作单位基本情况",
        "（二）在岗情况",
        "（三）岗位职能",
    )
    required_section4 = (
        "（一）对华态度",
        "（二）对所在国政治态度",
        "（三）对美政治态度",
    )
    if any(marker not in section1 for marker in required_section1):
        return False
    if any(marker not in section2 for marker in required_section2):
        return False
    if any(marker not in section4 for marker in required_section4):
        return False
    if "（一）" not in section5:
        return False
    return True


def follows_current_report_template_soft(content: str) -> bool:
    """写报收口放宽版：八章齐全；二级项多数命中即可，并接受家庭成员/工作单位等缩写标题。"""
    compact = (content or "").replace(" ", "").replace("\u3000", "")
    required_heads = (
        "一、基本情况",
        "二、在职在岗情况",
        "三、人脉资源",
        "四、政治立场",
        "五、污点劣迹",
        "六、公开表达与专业关注点",
        "七、身份核验与综合结论",
        "八、主要来源",
    )
    if any(head not in compact for head in required_heads):
        return False

    section1 = _extract_section(content, "一、基本情况", ("二、在职在岗情况",))
    section2 = _extract_section(content, "二、在职在岗情况", ("三、人脉资源",))
    section4 = _extract_section(content, "四、政治立场", ("五、污点劣迹",))
    section5 = _extract_section(content, "五、污点劣迹", ("六、公开表达与专业关注点",))

    # 允许常见缩写：家庭成员情况→家庭成员；工作单位基本情况→工作单位
    s1_markers = (
        "社交媒体",
        "（一）教育经历",
        "（二）工作经历",
        "（三）性格特点",
        ("（四）家庭成员情况", "（四）家庭成员"),
        "（五）经济状况",
    )
    s2_markers = (
        ("（一）工作单位基本情况", "（一）工作单位"),
        "（二）在岗情况",
        "（三）岗位职能",
    )
    s4_markers = (
        "（一）对华态度",
        "（二）对所在国政治态度",
        "（三）对美政治态度",
    )

    def _hit(section: str, marker) -> bool:
        if isinstance(marker, tuple):
            return any(m in section for m in marker)
        return marker in section

    s1_hit = sum(1 for m in s1_markers if _hit(section1, m))
    s2_hit = sum(1 for m in s2_markers if _hit(section2, m))
    s4_hit = sum(1 for m in s4_markers if _hit(section4, m))
    # 章节有实质正文也算过；否则至少命中多数二级项
    if len(section1) >= 40 and s1_hit >= 3:
        pass
    elif s1_hit >= 4:
        pass
    else:
        return False
    if not (len(section2) >= 30 or s2_hit >= 2):
        return False
    if not (len(section4) >= 30 or s4_hit >= 2):
        return False
    if not (len(section5) >= 20 or "（一）" in section5):
        return False
    return True


def is_final_report(content: str) -> bool:
    """合法步骤11终稿：够长、含≥2个旧章、且含五/六两章；以第一节开头；脏行先清洗再判定。

    新「一、基本情况」用 soft 模板验收：八章齐全且二级项大体覆盖即可，
    允许「家庭成员」「工作单位」等常见缩写标题入库，避免字面微差整单 failed。
    严格版 follows_current_report_template 仍供单测/校验对照。

    注意：步骤8/9/10 的独立块走 parse_standalone_analysis_blocks，不经过本函数。
    """
    body = prepare_final_report_body(content)
    if len(body) < 200:
        return False
    if not starts_with_report_section1(body):
        return False
    if has_report_dirty_meta(body):
        return False
    if _section_marker_hits(body) < 2:
        return False
    # 五、六为必含章节（可与第四章内容重叠）
    compact = (body or "").replace(" ", "").replace("\u3000", "")
    if _SECTION5_HEAD.replace(" ", "") not in compact:
        return False
    if _SECTION6_HEAD.replace(" ", "") not in compact:
        return False
    # 旧「一、账号基本信息」报告继续兼容；新「一、基本情况」走 soft 收口。
    if _SECTION1_HEAD.replace(" ", "") in compact:
        if not has_named_report_header(body):
            return False
        if not report_header_photo_valid(body):
            return False
        if not follows_current_report_template_soft(body):
            return False
    return True


def parse_standalone_analysis_blocks(text: str) -> Dict[str, str]:
    """解析独立步骤 8/9/10 正文块（不依赖 is_final_report，不受终稿门禁影响）。"""
    out: Dict[str, str] = {}
    mapping = {"8": "step6_basic", "9": "step6_voice", "10": "step6_basic"}
    for m in _STEP_BLOCK.finditer(text or ""):
        key = mapping.get(m.group(1))
        body = (m.group(2) or "").strip()
        if key and len(body) >= 200:
            out[key] = body
    return out


def _extract_section(text: str, start_marker: str, end_markers: Tuple[str, ...]) -> str:
    t = text or ""
    idx = t.find(start_marker)
    if idx < 0:
        return ""
    start = idx + len(start_marker)
    end = len(t)
    for em in end_markers:
        j = t.find(em, start)
        if j >= 0:
            end = min(end, j)
    return t[start:end].strip()


def backfill_analysis_from_report(text: str) -> Dict[str, str]:
    """从步骤十一终稿切片回填 9～10（步骤8 改由 collect_images 展示，不从终稿第一章回填）。

    仅对 is_final_report 通过的（已清洗）终稿切片；不合格不回填，避免污染 display。
    步骤8/9/10 若已由 standalone 块写入则不受影响。
    """
    if not is_final_report(text):
        return {}
    body = prepare_final_report_body(text)
    # 步骤8：图片流分析 → 详情接口读 collect_images，禁止把「一、账号基本信息」塞进 step8
    s9 = _extract_section(body, "三、账号网络活动情况", ("四、", "## 四"))
    s10 = _extract_section(body, "四、核查思路", ("五、", "## 五"))
    if not s10 and s9:
        s10 = s9
    out: Dict[str, str] = {}
    if s9:
        out["step6_voice"] = s9
    if s10:
        out["step6_basic"] = s10
    return out


def _has_post_evidence(text: str) -> bool:
    """章节/分析块是否含可展示的发文作证（避免只有观点标题、作证为空仍回填）。"""
    t = (text or "").strip()
    if len(t) < 80:
        return False
    # 典型作证句式
    if re.search(r"发文称[「\"]", t):
        return True
    if re.search(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", t):
        return True
    if re.search(r"发文作证\s*[：:]\s*\n\s*\d+\.", t):
        return True
    return False


def mentions_analysis_steps(text: str) -> bool:
    return bool(re.search(r"步骤\s*[89]|步骤\s*10|图片流分析|发文观点|涉华|圈层", text or "", re.I))


def looks_like_entering_analysis_text(text: str) -> bool:
    """是否明确进入步骤8/9/10（非进度句、非终稿）。"""
    t = (text or "").strip()
    if not t or len(t) < 40:
        return False
    if is_progress_only(t) or is_final_report(t):
        return False
    return bool(
        re.search(
            r"步骤\s*[89]\b|步骤\s*10\b|进入步骤\s*[89]|进入步骤\s*10|并行.*步骤\s*[89]",
            t,
            re.I,
        )
    )


def analysis_steps_terminal(status_map: Dict[str, str]) -> bool:
    for k in ANALYSIS_STEP_KEYS:
        if status_map.get(k) not in {"completed", "skipped"}:
            return False
    return True
