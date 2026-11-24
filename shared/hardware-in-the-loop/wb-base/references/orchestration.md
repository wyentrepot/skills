# 编排与页面

> 拆自 wb-base/SKILL.md（2026-11-18 拆薄）。只想直接跑一次全链路验证拿报告（无 token）或排查前端调用时读本文件；AI 日常任务用不到。

### §5.1 验证编排 REST（无鉴权，可选）

```bash
curl http://127.0.0.1:8790/api/scenarios               # 场景模板清单（/api/scenarios/<id>[/task]）
curl -X POST http://127.0.0.1:8790/api/run \
  -H "Content-Type: application/json" -d '<RunRequest，字段见 apps/workbench/orchestration/dto.py>'
# → 立即返回 run 视图（status=running），轮询 GET /api/run/<run_id> 到终态
#   passed / failed / cancelled / error / inconclusive
# 报告 GET /api/run/<id>/report；产物 GET /api/run/<id>/artifacts[/{artifact_id}]；取消 POST /api/run/<id>/cancel
```

- 其余：`GET /api/runs?limit≤200`（历史）、`POST /api/compare`、`POST /api/feedback`（比对/归因，不落 Run）。整链是烧录→监控→激励→比对→反馈→报告。
- 与 AI 控制面的取舍：要**授权审计/证据链/幂等**走 `/api/ai/v1`；只是**直接驱动一次全链路验证拿报告**，`/api/run` 更短（无 token、无 operation）。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/features.md

### §5.2 前端调用方映射（页面 → API 组 → 前缀机制）

| 前端文件 | 调用组 | 前缀机制 |
| --- | --- | --- |
| `pages/listener/{app,frames-pro}.js` | 侦听台日志/帧/串口/fs | **硬编码** `/api/listener/...`（独立版同逻辑硬编码 `/api/...`，两副本并存） |
| `pages/trace/trace.js` | 通信流追踪 + 帧详情 + indexes | 硬编码，注意双前缀 |
| `pages/dict/dict.js`、`pages/scenario/scenario.js`、`workbench.html` | 协议字典 / 编排 | 硬编码 `/api/dict`、`/api/...` |
| `pages/simcon/simcon.js` | 模拟集中器 + 构帧预览字典 | 硬编码 `/api/simcon` |
| `pages/module-serial/module-serial.js`（两副本） | 模块日志 + `/fs/*` + `/loghooks/*` | `API_BASE = body[data-api-base] ?? "/api"` ＋ 路径自带 `/module-serial` 命名空间 → 两形态通用 |
| `pages/serial-profile/serial-profile.js` | 串口 Profile | `API_BASE`（`/api`） |
| AI agent（无页面） | v2（默认）/ v1（专家兼容） | 直连 8790 `/api/ai/v2`；需要旧细粒度能力时 `/api/ai/v1` |

> 来源：ai-control-plane/references/api-contract.md

### §5.3 与页面操作的关系

AI 控制面复用与页面**同一套后端服务**（`ModuleSerialService` / listener service）：串口同一时刻独占，**页面与 AI 不能同时开同一串口**（409）。ADR-27 修的前端 bug（`ms-refresh-speed` 缺失导致实时日志页无反应）**不影响 API 行为**；主题/保活只影响页面观感（§8 G1/G2），与 AI 调用面无关。

> 来源：ai-control-plane/references/operation-guide.md

