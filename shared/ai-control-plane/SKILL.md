---
name: ai-control-plane
description: Control real hardware (HPLC meter-reading workbench) over HTTP as an AI. Covers obtaining an authorization token via the human-admin key, then driving serial sessions (cco/sta modules), firmware flashing, observation/evidence capture, and listener-frame queries through the workbench AI control plane at /api/ai/v1. Use when an AI agent needs to operate the 侦听台改造 workbench (serial ports, flash, log observation, evidence retrieval) programmatically, e.g. "用 AI 控制台向 cco/sta 发串口指令"、"AI 烧录固件并等结果"、"AI 观察日志并取证".
argument-hint: "[task, e.g. 监控cco日志直到出现XX / 向sta发送... / 烧录固件 / 跑验证用例]"
metadata:
  author: reasonix
  version: "2.1.0"
  applies-to: D:/2-侦听台改造
---

# AI 控制面 Skill（ai-control-plane）

驱动真机工作台（8790）的 HTTP 控制面。**按任务走最小路径：先查下表，只读对应的那一个
reference，用完即止——不要执行全流程。**（v2.0.0 起按需加载：本文件只做路由，
八步细节在各 references/*.md；完整手册 `docs/16-AI操作指南.md`。）
**例外**：下表「离线数据排查 / 漏点定位」是组合场景，允许一次读
`offline-analysis.md` + `cco-log.md` + `listener.md` 三个 reference（多端交叉验证需要）。

## 任务 → 最小路径速查

| 任务 | 最小调用链 | 需读（按需，只读一个） |
| --- | --- | --- |
| 监控日志 / 盯帧取证 | `observations` → `operations/{id}/wait` → `artifacts/{id}/content` | references/observations.md |
| 发串口指令（cco/sta） | `module-sessions/ensure` → `send`（→ `stop`） | references/module-serial.md |
| 烧录固件 | `flash-operations` → `wait` | references/module-serial.md |
| 验证用例 / 单步 / 查帧 | `simcon/verify·step` → `frames` | references/simcon.md |
| 查已解析帧 / 追踪一轮业务 | `listener/indexes…/frames`、`listener/traces` | references/listener.md |
| 离线数据排查 / 漏点定位 | **API 优先**：`listener/minute-periods` + `simcon/store/events|snapshots`；原始日志/CCO grep 才离线直查（组合场景，读 3 个） | references/offline-analysis.md（+ cco-log.md + listener.md） |
| 跑场景全链路 | `POST /api/run` → 轮询 → report | references/helpers.md |
| 查协议语义 / 构帧预检 | `/api/dict`、`/api/simcon/build` | references/helpers.md |
| 拿 token / 管授权 | `admin/grants`（**人来做**） | references/auth.md |

## 通用约定

- Base `http://127.0.0.1:8790`；`/api/ai/v1/*` 需 `Authorization: Bearer <token>`。
  token 由人签发（references/auth.md），**不要把 token 写进输出、日志或提交内容**。
- 探活：`GET /api/health`（免鉴权）；带 token 可 `GET /api/ai/v1/status` 看全局快照。
- 幂等：写操作一律带 `client_request_id`（或 `Idempotency-Key` 头），重复提交复用原操作。
- 长任务（烧录/观察/追踪/simcon verify）返回 202 + `operation_id`，用
  `GET /api/ai/v1/operations/{id}/wait?timeout_seconds≤30` 轮询到终态。
- 错误码：401 token 缺失/失效；403 越权/固件目录外/非本机发授权；404 资源不存在；
  **409 资源冲突（串口占用/会话冲突）不是故障**；422 参数非法；503 后端不可用/未配置。
- 侦听台深度解析三档 `parse_backend`（local/remote/none，REQS-0019）：`none` 时帧仍可查
  但无深度字段，先起 Windows 解析网关（桌面 `wsl环境部署.bat` → [4]，或
  `powershell -File uart-map.ps1 -Action start-gateway`；详见 references/listener.md）。

## 红线（行为边界）

1. **scope 最小化**：授权只申请本次任务需要的 scope（映射表见 references/auth.md）。
2. **用完即止**：完成本次任务即停——不开任务外的会话、不跑任务外的验证、不做"顺手"的全流程。
3. **串口独占**：同一物理串口同一时刻一个持有者（AI 与前端共享规则）；开了就关
   （stop/close 释放）；409 时等待或换口，不硬抢。
4. **观察先建后造**：先 `observations` 再制造目标事件（module_log 只盯创建之后的新日志）。
5. **授权归人**：`admin/grants` 只由人本机执行；AI 只使用已有 token，不自签、不扩权。
6. 不可取消的操作（烧录/verify）耐心等到终态，不并发重试。

## 参考

- 完整操作手册：`docs/16-AI操作指南.md`；接口契约总表：`docs/api-contract.md`；功能清单：`docs/features.md`
- 实现：`apps/workbench/ai_api.py`、`ai_operations.py`、`ai_auth.py`、`ai_store.py`
- 决策：DECISIONS.md ADR-28（开放 0.0.0.0 局域网监听）
