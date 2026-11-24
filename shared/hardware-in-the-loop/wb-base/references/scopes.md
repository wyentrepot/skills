# scope → 能力映射（14 种）与 v1 专家/兼容路径

> 拆自 wb-base/SKILL.md（2026-11-18 拆薄）。正文 §2.2 只留 scope 名单速览；签非烧录类任务的 grant 或维护 v1 旧客户端时读本文件。

### §2.2 scope → 能力映射（14 种）

| scope | 能力 | 所需资源 / 典型任务 |
| --- | --- | --- |
| `status:read` | `/status`、`/audit` | `*` 或资源；探状态、看审计流水 |
| `module_session:ensure` / `:stop` | 确保/创建、停止模块串口会话 | mapping_id / 会话 |
| `module_send:execute` | 向模块会话发送指令 | 会话 |
| `module_flash:execute` | 烧录固件 | 会话（另需 `firmware_roots`） |
| `listener:ensure` / `listener:stop` | 侦听台采集开 / 停 | mapping_id；停止时在线用当前 mapping_id、离线回退 `listener-main` |
| `listener:trace` | 创建通信流追踪（回放/live） | 当前侦听台 mapping_id / `listener-main` |
| `observation:create` | 建观察任务、取消操作 | mapping_id / 会话；监控日志、盯帧 |
| `evidence:read` | 读 operation / Artifact / 帧索引/追踪 | 对应资源；取证、查帧（监控行也必需） |
| `simcon:verify` / `simcon:send` / `simcon:read` | 验证任务 / 单步·开关串口 / 帧日志与持久层读 | `simcon` |
| `simeter:read` | 模拟电表状态/帧日志只读（v2 `simeter_frames.read`） | 模拟电表观察；写操作免 token 直连 `/api/simeter/*` |

**资源（resource）**：串口类用 `serial_ports.json` 的 `mapping_id`：`cco-main`、`sta-main`、`listener`（实际 COM 号随接线变化，**调用方优先用 mapping_id，不硬编码 COM 号**）；simcon 口的 task **必须显式 `mapping_id:"simcon"`**（不传会自选 `/dev/ttyS0` 报 `Input/output error`，见 `wb-simcon` §1；该口实测 115200，baud 以 status 的 `mapping.baudrate` 为准）；会话资源用 `session_id`（`ms-xxxx`），AI 接口内部归一到其 `mapping_id`。`resources:["*"]` 全放行（谨慎）；越权 403，token 无效/过期/撤销 401。

> 来源：ai-control-plane/references/auth.md；ai-control-plane/references/operation-guide.md；ai-control-plane/references/simeter.md；ai-control-plane/references/auth.md


---
### §3.7 v1 专家/兼容路径

v1 语义：每接口校验 **scope + resource**；长任务返回 `operation_id` 轮询到终态；幂等同 v2；烧录强制 `firmware_roots` 白名单。

| 能力 | 端点组（前缀 `/api/ai/v1`） | scope |
| --- | --- | --- |
| 全局状态 / 审计 | `GET /status`、`GET /audit` | `status:read` |
| 模块会话 | `POST /module-sessions/ensure`、`{id}/stop`、`{id}/send` | `module_session:ensure` / `:stop` / `module_send:execute` |
| 烧录 | `POST /flash-operations`（202） | `module_flash:execute` |
| 侦听台控制 / 追踪 | `POST /listener/ensure`、`/listener/stop`；`GET /listener/schema`；`POST`/`GET /listener/traces[/{id}]` | `listener:ensure`/`stop`、`evidence:read`、`listener:trace` |
| 观察 | `POST /observations`（202，支持 `Idempotency-Key`） | `observation:create` |
| 操作与证据 | `GET /operations/{id}[/wait·/cancel]`、`GET /artifacts/{id}[/content]` | `evidence:read`（cancel 需 `observation:create`） |
| 帧索引 / 分钟分桶 | `GET /listener/indexes`、`/{id}/frames[/{frame_id}]`、`/listener/minute-periods` | `evidence:read` |
| 模拟集中器 | `POST /simcon/verify`、`/simcon/step`、`/simcon/open`/`close`；`GET /simcon/frames`、`/simcon/session`、`/simcon/store/events`、`/simcon/store/snapshots[/{id}]` | `simcon:verify` / `simcon:send` / `simcon:read` |

v1 专家 checklist（逐步控制串口或维护旧客户端时才用）：`POST /admin/grants` 拿 token（人做）→ `GET /status` 确认后端就绪与串口在线 → `POST /module-sessions/ensure` → `POST /flash-operations`/`POST /observations`/`POST /simcon/verify` → `GET /operations/{id}/wait` 到终态 → `GET /artifacts/{id}/content` 取证据正文 → 收尾 `POST /module-sessions/{id}/stop`、`/listener/stop`、`/simcon/close`。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

