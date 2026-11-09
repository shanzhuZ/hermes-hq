# 在本仓库根目录下运行 hermes CLI / gateway，确保读取仓库内 config.yaml。
# 用法：
#   .\scripts\hermes.ps1 chat
#   .\scripts\hermes.ps1 gateway
#   .\scripts\hermes.ps1 hooks list

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:HERMES_HOME = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { $RepoRoot }

# Windows 本机默认（可用外部环境变量覆盖）；Linux 请用 scripts/hermes.sh
if (-not $env:HERMES_PYTHON) {
    if (Test-Path "D:/environment/python/python.exe") {
        $env:HERMES_PYTHON = "D:/environment/python/python.exe"
    } else {
        $py = (Get-Command python -ErrorAction SilentlyContinue)
        if ($py) { $env:HERMES_PYTHON = $py.Source }
    }
}
if (-not $env:HERMES_NODE) {
    if (Test-Path "C:/nvm4w/nodejs/node.exe") {
        $env:HERMES_NODE = "C:/nvm4w/nodejs/node.exe"
    } else {
        $node = (Get-Command node -ErrorAction SilentlyContinue)
        if ($node) { $env:HERMES_NODE = $node.Source }
    }
}

if (-not $env:MCP_WEIBO_CMD) {
    $env:MCP_WEIBO_CMD = "D:/environment/python/Scripts/mcp-server-weibo.exe"
}
if (-not $env:MCP_WEIXIN_SEARCH_CMD) {
    $env:MCP_WEIXIN_SEARCH_CMD = "D:/environment/python/Scripts/weixin_search_mcp.exe"
}
if (-not $env:MCP_TRENDS_HUB_CMD) {
    $env:MCP_TRENDS_HUB_CMD = "D:/environment/node/node_cache/mcp-trends-hub.cmd"
}
if (-not $env:MCP_REDDIT_CMD) {
    $env:MCP_REDDIT_CMD = "D:/environment/node/node_cache/reddit-mcp-buddy.cmd"
}
if (-not $env:MCP_FIRECRAWL_CMD) {
    $env:MCP_FIRECRAWL_CMD = "D:/environment/node/node_cache/firecrawl-mcp.cmd"
}
if (-not $env:MCP_PLAYWRIGHT_CMD) {
    $env:MCP_PLAYWRIGHT_CMD = "D:/environment/node/node_cache/playwright-mcp.cmd"
}
if (-not $env:MCP_APIFY_CMD) {
    $env:MCP_APIFY_CMD = "D:/environment/node/node_cache/actors-mcp-server.cmd"
}

if (-not $env:TWITTER_COOKIES) {
    $env:TWITTER_COOKIES = Join-Path $env:USERPROFILE ".config\twitter-mcp\cookies.json"
}
if (-not $env:TESSERACT_CMD) {
    $env:TESSERACT_CMD = "C:/Program Files/Tesseract-OCR/tesseract.exe"
}
if (-not $env:HERMES_IMAGE_LOCAL_DIR) {
    $env:HERMES_IMAGE_LOCAL_DIR = Join-Path $env:HERMES_HOME "data\image_bytes"
}
if (-not $env:HERMES_VIDEO_LOCAL_DIR) {
    $env:HERMES_VIDEO_LOCAL_DIR = Join-Path $env:HERMES_HOME "data\video_bytes"
}

Write-Host "HERMES_HOME=$($env:HERMES_HOME)" -ForegroundColor DarkGray
& hermes @args
