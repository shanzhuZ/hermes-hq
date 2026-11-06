# hermes-hq

从 `hermes-xa` 复制并裁剪的写报专用工程。

## 范围

- **保留**：04 画像写报（`scripts/report_04`、`account-intelligence-report`、相关 Java 建任务与共享入库层）
- **已删除**：01 采集 / 02 扩建 / 03 核查 / 05 自定义 的业务包、Skill、建任务入口
- **暂留共享库**：`scripts/collect_01` 中的 `db` / `normalizers` / `display_store` 等（`report_04` 仍依赖，后续可再抽离改造）

## 本地路径

默认工作目录：`D:\hermes-hq`。改造前请将 `HERMES_HOME`、`.env`、`config.yaml` 中的路径按本目录调整。
