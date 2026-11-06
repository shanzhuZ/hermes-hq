---
name: account-intelligence-report
description: "hermes-hq 04公开资料核查。主账号→Maigret跨平台→账号认定→公开信息检索备料→全账号发文→八章报告。"
version: 3.0.0
author: hermes-hq
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [account-intelligence, report, osint]
    related_skills: [image-asset-analysis]
---

# 04 · 公开资料核查报告（hermes-hq）

**任务**：主账号采集 → Maigret 跨平台检索 → 账号认定 → 公开网页备料（不搜账号）→ 已认定账号发文 → 八章成稿。

## 启动
`skill_view` → **`references/collect-rules.yaml`**（唯一参考）。

## 铁律
- **全程简体中文**；每步以「步骤X：…」呈现；不可跳步
- **步骤2** 必须用 `mcp_maigret_*`；禁止用 `web_search` 代替跨平台找账号
- **步骤4** 仅 `web_search` / `web_extract` / `browser_*`，只为八章备料；**禁止**再搜其它社交账号
- 无可靠公开证据写 **「未核实」**；终稿允许带来源链接
- 终稿必须以文首标题或「一、基本情况」起笔

## 执行流程（v3）

| 步骤 | 节点 | 动作 |
|------|------|------|
| 1 | `step1_seed` | 主账号主页（仅种子平台） |
| 2 | `step2_maigret` | Maigret 跨平台账号检索 |
| 3 | `step3_identity` | 账号认定（`[账号认定结论]`）；可采候选主页佐证 |
| 4 | `step4_osint_web` | 公开信息检索（八章备料，不扩账号） |
| 5 | `step5_posts` | 已认定账号发文采样 |
| 6 | `step7_report` | 八章公开资料核查报告 |

**本版不含**：ES/PDL 专步、媒体专步、六专题中间步、旧「网页发现后再采主页」倒序。

## 步骤 6 输出骨架（八章）

```
{姓名} 公开资料核查报告
（原名：…；曾用名核验说明）

照片来源说明：…
资料范围：… 核查日期：…

## 一、基本情况
…
## 二、在职在岗情况
…
## 三、人脉资源
…
## 四、政治立场
…
## 五、污点劣迹
…
## 六、公开表达与专业关注点
…
## 七、身份核验与综合结论
…
## 八、主要来源
1. …
```

## 步骤要点
- **1**：只采用户指定主账号，不扩平台。
- **2**：Maigret 出候选清单。
- **3**：认定归属；种子平台不要重复主页采集。
- **4**：按模板章节 `web_search`，不为找账号。
- **5**：对已认定账号必须实调发文工具。
