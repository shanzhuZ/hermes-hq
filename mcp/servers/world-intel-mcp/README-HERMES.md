# world-intel-mcp（Hermes 接入说明）

上游：https://github.com/marc-shade/world-intel-mcp  
本地：`mcp/servers/world-intel-mcp`  
配置：`config.yaml` → `mcp_servers.world_intel`

## 安装（本机已做过可跳过）

```bash
cd D:/hermes-xa/mcp/servers/world-intel-mcp
D:/environment/python/python.exe -m pip install -e .
```

可选：

```bash
# 向量库语义检索（需本机 Qdrant）
D:/environment/python/python.exe -m pip install -e ".[vector]"
# 看板
D:/environment/python/python.exe -m pip install -e ".[dashboard]"
```

## Hermes 配置要点

- 入口：`D:/environment/python/Scripts/world-intel-mcp.exe`（stdio）
- 代理：沿用 `HTTP_PROXY` / `HTTPS_PROXY`（国内访问公共情报源通常需要）
- **默认只开放约 25 个写报/OSINT 常用工具**（`tools.include`），避免 113 个工具撑爆上下文
- 需要全量工具时：删掉 `config.yaml` 里该段的 `tools.include` 后重启 Gateway

## 可选环境变量（`.env`）

见 `.env.example` 中 `ACLED_ACCESS_TOKEN` / `FRED_API_KEY` 等；不填时多数免费公共 API 仍可用，部分源会降级或为空。

## 重启

改 `config.yaml` 后需重启 Hermes Gateway / Agent 进程才会加载新 MCP。
