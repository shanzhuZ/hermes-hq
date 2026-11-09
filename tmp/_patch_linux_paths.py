# -*- coding: utf-8 -*-
"""一次性把 Windows 绝对路径改成 ${ENV} 占位，便于 Linux/Windows 共用。"""
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
MCP_YAML = Path(__file__).resolve().parent.parent / "mcp" / "mcp_servers.yaml"

CONFIG_REPLS = [
    (
        "D:/environment/python/python.exe D:/hermes-hq/scripts/db_sink.py",
        "${HERMES_PYTHON} ${HERMES_HOME}/scripts/db_sink.py",
    ),
    ("D:/environment/python/Scripts/mcp-server-weibo.exe", "${MCP_WEIBO_CMD}"),
    ("D:/environment/python/Scripts/weixin_search_mcp.exe", "${MCP_WEIXIN_SEARCH_CMD}"),
    ("D:/environment/python/python.exe", "${HERMES_PYTHON}"),
    (
        "D:/hermes-hq/mcp/servers/weixin-read-mcp/src/server.py",
        "${HERMES_HOME}/mcp/servers/weixin-read-mcp/src/server.py",
    ),
    ("PATH: C:/Users/zhr/.url-md/bin;${PATH}", "PATH: ${PATH}"),
    ("D:/environment/node/node_cache/mcp-trends-hub.cmd", "${MCP_TRENDS_HUB_CMD}"),
    (
        "D:/hermes-hq/mcp/servers/bilibili-mcp-server/server.py",
        "${HERMES_HOME}/mcp/servers/bilibili-mcp-server/server.py",
    ),
    ("D:/environment/node/node_cache/reddit-mcp-buddy.cmd", "${MCP_REDDIT_CMD}"),
    ("D:/environment/node/node_cache/firecrawl-mcp.cmd", "${MCP_FIRECRAWL_CMD}"),
    ("D:/environment/node/node_cache/playwright-mcp.cmd", "${MCP_PLAYWRIGHT_CMD}"),
    ("D:/environment/node/node_cache/actors-mcp-server.cmd", "${MCP_APIFY_CMD}"),
    (
        "D:/hermes-hq/mcp/servers/maigret-mcp-server/server.py",
        "${HERMES_HOME}/mcp/servers/maigret-mcp-server/server.py",
    ),
    (
        "MAIGRET_REPORTS_DIR: D:/hermes-hq/mcp/data/maigret-reports",
        "MAIGRET_REPORTS_DIR: ${HERMES_HOME}/mcp/data/maigret-reports",
    ),
    (
        "D:/hermes-hq/mcp/servers/user-scanner-mcp-server/run_user_scanner_mcp.py",
        "${HERMES_HOME}/mcp/servers/user-scanner-mcp-server/run_user_scanner_mcp.py",
    ),
    (
        "D:/hermes-hq/mcp/servers/pdl-person-mcp-server/server.py",
        "${HERMES_HOME}/mcp/servers/pdl-person-mcp-server/server.py",
    ),
    (
        "D:/hermes-hq/mcp/servers/twitter-mcp-server/run_twitter_mcp_data_only.py",
        "${HERMES_HOME}/mcp/servers/twitter-mcp-server/run_twitter_mcp_data_only.py",
    ),
    (
        "TWITTER_COOKIES: C:/Users/zhr/.config/twitter-mcp/cookies.json",
        "TWITTER_COOKIES: ${TWITTER_COOKIES}",
    ),
    (
        "D:/hermes-hq/mcp/servers/ocr-mcp-server/run_ocr_mcp.py",
        "${HERMES_HOME}/mcp/servers/ocr-mcp-server/run_ocr_mcp.py",
    ),
    (
        "TESSERACT_CMD: C:/Program Files/Tesseract-OCR/tesseract.exe",
        "TESSERACT_CMD: ${TESSERACT_CMD}",
    ),
    (
        "TESSDATA_PREFIX: D:/hermes-hq/mcp/servers/ocr-mcp-server/tessdata",
        "TESSDATA_PREFIX: ${HERMES_HOME}/mcp/servers/ocr-mcp-server/tessdata",
    ),
    ("C:/nvm4w/nodejs/node.exe", "${HERMES_NODE}"),
    (
        "D:/hermes-hq/mcp/servers/youtube-mcp-server/dist/stdio-main.js",
        "${HERMES_HOME}/mcp/servers/youtube-mcp-server/dist/stdio-main.js",
    ),
]

MCP_REPLS = [
    ("D:/environment/python/Scripts/mcp-server-weibo.exe", "${MCP_WEIBO_CMD}"),
    ("D:/environment/python/Scripts/weixin_search_mcp.exe", "${MCP_WEIXIN_SEARCH_CMD}"),
    ("D:/environment/python/python.exe", "${HERMES_PYTHON}"),
    ("D:/hermes-xa/mcp/", "${HERMES_HOME}/mcp/"),
    ("PATH: C:/Users/zhr/.url-md/bin;${PATH}", "PATH: ${PATH}"),
    ("D:/environment/node/node_cache/mcp-trends-hub.cmd", "${MCP_TRENDS_HUB_CMD}"),
    ("D:/environment/node/node_cache/reddit-mcp-buddy.cmd", "${MCP_REDDIT_CMD}"),
    ("D:/environment/node/node_cache/firecrawl-mcp.cmd", "${MCP_FIRECRAWL_CMD}"),
    ("D:/environment/node/node_cache/playwright-mcp.cmd", "${MCP_PLAYWRIGHT_CMD}"),
    ("D:/environment/node/node_cache/actors-mcp-server.cmd", "${MCP_APIFY_CMD}"),
    (
        "TWITTER_COOKIES: C:/Users/zhr/.config/twitter-mcp/cookies.json",
        "TWITTER_COOKIES: ${TWITTER_COOKIES}",
    ),
    (
        "TESSERACT_CMD: C:/Program Files/Tesseract-OCR/tesseract.exe",
        "TESSERACT_CMD: ${TESSERACT_CMD}",
    ),
    ("C:/nvm4w/nodejs/node.exe", "${HERMES_NODE}"),
]


def apply(path: Path, repls) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in repls:
        cnt = text.count(old)
        if cnt == 0:
            print(f"[MISS] {path.name}: {old[:70]}")
        else:
            text = text.replace(old, new)
            print(f"[OK x{cnt}] {path.name}: {old[:50]} -> {new[:50]}")
    # 注释里的 Windows 路径说明
    text = text.replace("D:/hermes-xa/mcp/", "${HERMES_HOME}/mcp/")
    text = text.replace("D:/hermes-hq", "${HERMES_HOME}")
    path.write_text(text, encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    apply(CONFIG, CONFIG_REPLS)
    if MCP_YAML.is_file():
        apply(MCP_YAML, MCP_REPLS)
