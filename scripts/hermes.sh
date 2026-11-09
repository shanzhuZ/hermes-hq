#!/usr/bin/env bash
# 在本仓库根目录下运行 hermes CLI / gateway，确保读取仓库内 config.yaml。
# 用法：
#   ./scripts/hermes.sh chat
#   ./scripts/hermes.sh gateway
#   ./scripts/hermes.sh hooks list
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HERMES_HOME="${HERMES_HOME:-$REPO_ROOT}"

# 跨平台运行时默认值（可用外部环境变量覆盖）
export HERMES_PYTHON="${HERMES_PYTHON:-$(command -v python3 || command -v python)}"
export HERMES_NODE="${HERMES_NODE:-$(command -v node || true)}"
export HERMES_NPX="${HERMES_NPX:-$(command -v npx || true)}"

# MCP 可执行文件：Linux 上一般为 PATH 中的 console_script / npm bin（无 .exe/.cmd）
export MCP_WEIBO_CMD="${MCP_WEIBO_CMD:-mcp-server-weibo}"
export MCP_WEIXIN_SEARCH_CMD="${MCP_WEIXIN_SEARCH_CMD:-weixin_search_mcp}"
export MCP_TRENDS_HUB_CMD="${MCP_TRENDS_HUB_CMD:-mcp-trends-hub}"
export MCP_REDDIT_CMD="${MCP_REDDIT_CMD:-reddit-mcp-buddy}"
export MCP_FIRECRAWL_CMD="${MCP_FIRECRAWL_CMD:-firecrawl-mcp}"
export MCP_PLAYWRIGHT_CMD="${MCP_PLAYWRIGHT_CMD:-playwright-mcp}"
export MCP_APIFY_CMD="${MCP_APIFY_CMD:-actors-mcp-server}"

export TWITTER_COOKIES="${TWITTER_COOKIES:-$HOME/.config/twitter-mcp/cookies.json}"
export TESSERACT_CMD="${TESSERACT_CMD:-tesseract}"

# 本地媒体目录（Java / Python 共用相对路径约定）
export HERMES_IMAGE_LOCAL_DIR="${HERMES_IMAGE_LOCAL_DIR:-$HERMES_HOME/data/image_bytes}"
export HERMES_VIDEO_LOCAL_DIR="${HERMES_VIDEO_LOCAL_DIR:-$HERMES_HOME/data/video_bytes}"

echo "HERMES_HOME=$HERMES_HOME" >&2
exec hermes "$@"
