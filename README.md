# hermes-hq

从 `hermes-xa` 复制并裁剪的写报专用工程。

## 范围

- **保留**：04 画像写报（`scripts/report_04`、`account-intelligence-report`、相关 Java 建任务与共享入库层）
- **已删除**：01 采集 / 02 扩建 / 03 核查 / 05 自定义 的业务包、Skill、建任务入口
- **暂留共享库**：`scripts/collect_01` 中的 `db` / `normalizers` / `display_store` 等（`report_04` 仍依赖，后续可再抽离改造）

## 本地路径 / 跨平台部署

`config.yaml` / `mcp/mcp_servers.yaml` 中的解释器与 MCP 命令已改为 `${HERMES_HOME}`、`${HERMES_PYTHON}`、`${MCP_*_CMD}` 等环境变量占位，避免写死 Windows 盘符。

- **Windows**：`.\scripts\hermes.ps1 chat|gateway`（自动填本机默认路径）
- **Linux/Ubuntu**：`chmod +x scripts/hermes.sh && ./scripts/hermes.sh chat|gateway`
- 部署前复制 `.env.example` → `.env`，按服务器填写 `HERMES_HOME`、MCP 可执行文件、cookies、tesseract 等

媒体目录默认相对路径 `data/image_bytes`、`data/video_bytes`（可用 `HERMES_IMAGE_LOCAL_DIR` / `HERMES_VIDEO_LOCAL_DIR` 覆盖）。
