"""从 collect_posts 为某平台选出「最新一条可下载视频」。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from collect_01 import db

_YOUTUBE_RE = re.compile(
    r"(https?://(?:www\.)?(?:youtube\.com/watch\?[^\s\"'<>]+|youtu\.be/[^\s\"'<>]+))",
    re.I,
)
_DIRECT_VIDEO_RE = re.compile(
    r"(https?://[^\s\"'<>]+\.(?:mp4|webm|mov|m4v|mkv)(?:\?[^\s\"'<>]*)?)",
    re.I,
)
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".avif")
_VIDEO_EXT = (".mp4", ".webm", ".m4v", ".mov", ".mkv")


def _parse_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except Exception:
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            t = text
            if fmt.endswith("%z") and t.endswith("Z"):
                t = t[:-1] + "+0000"
            if fmt.endswith("Z") and t.endswith("Z"):
                return datetime.strptime(t, fmt)
            return datetime.strptime(t, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _is_youtube(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be", "music.youtube.com"} or host.endswith(
        ".youtube.com"
    )


def _path_lower(url: str) -> str:
    try:
        return (urlparse(url).path or "").lower()
    except Exception:
        return str(url or "").lower()


def _is_image_url(url: str) -> bool:
    """静态图直链（含 Twitter pbs.twimg.com/media/*.jpg），禁止当视频。"""
    if not url:
        return False
    path = _path_lower(url)
    if any(path.endswith(ext) for ext in _IMAGE_EXT):
        return True
    low = str(url).lower()
    # CDN 查询串前已带扩展名：.../xxx.jpg?name=orig
    return any(f"{ext}?" in low or f"{ext}&" in low for ext in _IMAGE_EXT)


def _is_video_like_url(url: str) -> bool:
    """可交给下载器的视频线索：YouTube 页 / 视频直链。不含静态图。"""
    if not url or not str(url).startswith("http"):
        return False
    if _is_image_url(url):
        return False
    if _is_youtube(url):
        return True
    path = _path_lower(url)
    if any(path.endswith(ext) for ext in _VIDEO_EXT):
        return True
    low = str(url).lower()
    return any(f"{ext}?" in low or f"{ext}&" in low for ext in _VIDEO_EXT)


def _urls_from_text(text: str) -> List[str]:
    out: List[str] = []
    if not text:
        return out
    for m in _YOUTUBE_RE.finditer(text):
        out.append(m.group(1).rstrip(").,;]}"))
    for m in _DIRECT_VIDEO_RE.finditer(text):
        out.append(m.group(1).rstrip(").,;]}"))
    return [u for u in out if _is_video_like_url(u)]


def _media_types_hint(*blobs: Any) -> List[str]:
    """从 raw / media_json 收集 media type 提示。"""
    found: List[str] = []
    for blob in blobs:
        if blob is None:
            continue
        data = _parse_json(blob) if not isinstance(blob, (dict, list)) else blob
        if isinstance(data, dict):
            types = data.get("media_types") or []
            if isinstance(types, str):
                types = [types]
            if isinstance(types, list):
                found.extend(str(t) for t in types)
            media = data.get("media")
            if isinstance(media, list):
                for m in media:
                    if isinstance(m, dict):
                        found.append(str(m.get("type") or m.get("media_type") or ""))
                    elif isinstance(m, str) and m.startswith("http"):
                        found.append("photo" if _is_image_url(m) else "unknown")
            if data.get("has_video"):
                found.append("video")
        elif isinstance(data, list):
            for m in data:
                if isinstance(m, dict):
                    found.append(str(m.get("type") or m.get("media_type") or ""))
                elif isinstance(m, str) and m.startswith("http"):
                    found.append("photo" if _is_image_url(m) else "unknown")
    return found


def _twitter_has_video(raw: Any, media_json: Any = None) -> bool:
    types = [str(t).lower() for t in _media_types_hint(raw, media_json) if t]
    if any(t in {"video", "animated_gif", "gif"} for t in types):
        return True
    if isinstance(raw, dict) and bool(raw.get("has_video")):
        return True
    return False


def _dig_urls(obj: Any, depth: int = 0) -> List[str]:
    if depth > 5 or obj is None:
        return []
    out: List[str] = []
    if isinstance(obj, str):
        if obj.startswith("http"):
            if _is_video_like_url(obj):
                out.append(obj)
            else:
                out.extend(_urls_from_text(obj))
        return out
    if isinstance(obj, dict):
        # 优先常见视频字段；泛化 url 必须过视频白名单，避免 jpg 配图混入
        for key in (
            "videoUrl",
            "video_url",
            "webVideoUrl",
            "downloadAddr",
            "playAddr",
            "stream_url",
            "mp4_hd_url",
            "mp4_sd_url",
            "content_url",
            "url",
        ):
            val = obj.get(key)
            if isinstance(val, str) and val.startswith("http") and _is_video_like_url(val):
                out.append(val)
        for v in obj.values():
            out.extend(_dig_urls(v, depth + 1))
        return out
    if isinstance(obj, list):
        for it in obj[:50]:
            out.extend(_dig_urls(it, depth + 1))
    return out


def extract_video_url_from_post(row: Dict[str, Any]) -> Optional[str]:
    """从单条发文解析可下载视频 URL（YouTube 页 / 直链 / 平台页）。

    禁止把静态配图（jpg/png 等）当成视频，否则会出现 1 帧 / 0s。
    """
    platform = str(row.get("platform") or "").lower()
    content_url = str(row.get("content_url") or "").strip()
    content_type = str(row.get("content_type") or "").lower()
    text = str(row.get("content_text") or "")
    raw = _parse_json(row.get("raw_json"))
    media_json = row.get("media_json")

    # 1) 正文/外链里的 YouTube / 视频直链
    for u in _urls_from_text(text):
        return u
    if content_url and _is_youtube(content_url):
        return content_url

    # 2) YouTube 平台发文：watch 页即视频
    if platform == "youtube" and content_url:
        return content_url
    if platform == "youtube" and isinstance(raw, dict):
        vid = str(raw.get("videoId") or raw.get("id") or "").strip()
        if vid and not vid.startswith("http"):
            return f"https://www.youtube.com/watch?v={vid}"

    # 3) Twitter：仅当媒体类型明确是视频/GIF 时，用状态页走 yt-dlp
    if platform == "twitter":
        if _twitter_has_video(raw, media_json):
            raw_id = raw.get("id") if isinstance(raw, dict) else None
            tid = str(row.get("content_id") or raw_id or "").strip()
            if content_url and not _is_image_url(content_url):
                return content_url
            if tid:
                return f"https://twitter.com/i/status/{tid}"
        # 纯图片帖：不再深挖 media.url（jpg）
        for u in _dig_urls(raw):
            if _is_youtube(u) or _is_video_like_url(u):
                return u
        return None

    # 4) 直链 / raw 深挖（仅视频形态）
    if content_url and _is_video_like_url(content_url):
        return content_url
    dug = _dig_urls(raw)
    for u in dug:
        if _is_video_like_url(u):
            return u
    # TikTok / IG 等：content_type 声明为 video 且非图片直链
    if content_type == "video" and content_url and not _is_image_url(content_url):
        return content_url
    return None


def _sort_key(row: Dict[str, Any]) -> datetime:
    raw = _parse_json(row.get("raw_json")) or {}
    pub = row.get("published_at")
    dt = _parse_dt(pub)
    if dt:
        return dt
    if isinstance(raw, dict):
        for k in ("publishedAt", "published_at", "created_at", "create_at", "date"):
            dt = _parse_dt(raw.get(k))
            if dt:
                return dt
    return _parse_dt(row.get("created_at")) or datetime.min


def select_latest_downloadable_video(task_id: str, platform: str) -> Optional[Dict[str, Any]]:
    """返回 {url, post_id, account_id, content_url, published_at} 或 None。"""
    rows = db.fetch_all(
        """
        SELECT platform, account_id, content_id, content_type, content_url, content_text,
               published_at, created_at, raw_json, media_json
        FROM collect_posts
        WHERE task_id=%s AND platform=%s
        ORDER BY id DESC
        LIMIT 200
        """,
        (task_id, platform),
    ) or []
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        url = extract_video_url_from_post(row)
        if not url:
            continue
        candidates.append(
            {
                "url": url,
                "post_id": str(row.get("content_id") or ""),
                "account_id": str(row.get("account_id") or ""),
                "content_url": row.get("content_url"),
                "published_at": row.get("published_at"),
                "created_at": row.get("created_at"),
                "raw_json": row.get("raw_json"),
                "_sort": _sort_key(row),
            }
        )
    if not candidates:
        return None
    candidates.sort(key=lambda x: x["_sort"], reverse=True)
    best = candidates[0]
    best.pop("_sort", None)
    best.pop("raw_json", None)
    return best
