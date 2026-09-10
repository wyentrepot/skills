# AI 操作指南（默认 AI 控制面 `/api/ai/v2`；v1 专家兼容）

> 面向 AI 客户端 / agent 的使用手册：如何让 AI 通过 HTTP 控制真机（模块日志串口、侦听台、烧录、观察比对、证据取证）。
> 默认入口是任务级 v2：用一次任务请求替代多次底层接口拼接；既有 `/api/ai/v1` 保留在本文后半部分，供专家诊断和旧客户端兼容。
> 代码事实来源：`apps/workbench/ai_v2_api.py`、`ai_capability_service.py`、`ai_contracts.py`，以及 v1 的 `ai_api.py`、`ai_operations.py`、`ai_auth.py`、`ai_store.py`。

## 1. 什么是 AI 控制面

AI 控制面是 workbench（AI 网页工作台，默认端口 `8790`）暴露给 **AI 使用者的 REST 控制面**。
人可以用页面点按钮操作真机；AI 则通过这组 API 完成同样的操作，并拿到可复核的证据（Artifact）。

- 默认入口：`http://127.0.0.1:8790/api/ai/v2`
- v1 专家入口：`http://127.0.0.1:8790/api/ai/v1`
- v1 业务接口需要 `Authorization: Bearer <token>`（admin 授权接口用 `X-Workbench-Admin-Key`）；v2 本机全权限按下述 loopback 开关判定
- 本机启用 `WORKBENCH_LOCAL_FULL_ACCESS=1` 时，真实 loopback 请求可直接使用 v2 全能力；局域网仍须 Bearer grant
- v2 所有写操作都有 **audit 审计**；统一返回 `job_id`，按需读取 job/evidence，避免 AI 拼接多条底层接口

### 1.1 默认 v2：四步低 token 任务流

v2 只有八条公开路径：`capabilities`、`investigations`、`verification-runs`、
`module-actions`、`flash-jobs`、`jobs/{job_id}`、`jobs/{job_id}/cancel` 和
`jobs/{job_id}/evidence`。AI 通常只需以下调用链：

1. `GET /api/ai/v2/capabilities`：发现后端和逻辑资源 alias；不要读取或猜测物理 COM 号。
2. 提交一个任务：观察用 `POST /investigations`，模块控制用 `POST /module-actions`，验证用
   `POST /verification-runs`，烧录用 `POST /flash-jobs`。
3. `GET /api/ai/v2/jobs/{job_id}?wait_seconds=0`：读取统一状态；GET 不推进任务，也不产生副作用。
4. 只有需要细节时才调用 `GET /api/ai/v2/jobs/{job_id}/evidence?level=L1|L2|L3`。

示例：一次并行观察模块日志和侦听台历史索引（最多 3 个 observation）：

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v2/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "case-20260902-001",
    "client_request_id": "case-20260902-001-observe",
    "observations": [
      {"source":"module_log", "target":{"session_id":"ms-xxxx"},
       "window":{"mode":"live","timeout_seconds":120},
       "match":{"kind":"literal","value":"发送成功"}},
      {"source":"listener", "target":{"index_id":"idx-20260902"},
       "window":{"mode":"historical","index_id":"idx-20260902","start_frame_id":1,"end_frame_id":500},
       "match":{"kind":"literal","value":"上行"}}
    ],
    "cleanup":"owned_only"
  }'
```

返回 `202` 和 `job_id`。历史窗口完成后可立即读 job；live 窗口由服务端 worker 推进。
`job_state` 表示任务执行状态，`verdict` 只表示观察/验证结论（`pass/fail/inconclusive/error`）。
模块动作和烧录成功不会伪装成业务 `pass`。

证据按需升级：先取 L1 摘要，再按判断需要取 L2 受限明细，最后用 L3 稳定引用定位原始帧或
Artifact。历史日志必须保留 `index_id`；实时 `not_seen` 没有可信到达时间时只能是
`inconclusive`（`live_window_unverified`），不能据此证明“没有发生”。

**listener 语义查询与分层证据（REQS-0022）**：listener observation 的 `match.kind`
除 `parsed_frame` / `frame_query` 外，新增两个语义查询，均复用既有能力、不新建索引：

- `trace_query`：复用 `TraceService.run_replay`，查并发抄表/单表/00A1/0020/0008 的
  多跳通信流。`feature` 给 `app_id`（必填）/`msg_seq`/`frm_type`/`dst_tei`/`nid`/
  `channel`/`app_raw_contains`/`raw_hex_contains`；`scope` 为 `flow`/`round`/`campaign`；
  `directions` 为 L2 展示筛选（`downlink`/`uplink`/`ack`）。`raw_hex_contains` 仅作
  末端验证，删除空白后须为 2–512 个偶数长度十六进制字符，**无 `app_id`/NID/时间窗/
  帧 ID 窗口任一收窄条件时返回 422**。
- `minute_periods`：复用 `list_task_minute_periods`，查分钟采集。`match` 给
  `task_no`（必填）/`period_minutes`/`cco_tei`/`nid`；窗口仅 `time_range`。业务归属
  **以 `freeze_time` 为准**，L2 同时给出 `log_time` 与 `freeze_time`，不得用上报时间替代。

`GET /jobs/{job_id}/evidence` 三级投影：L1 范围摘要（index_id/时间窗/过滤器/总帧数/
按帧类型与方向计数/通信流组数/`correlation_status`/解析后端/可下钻 refs，≤3 KiB，**无 raw_hex**）；
L2 解析投影（≤16 KiB 且 ≤50 条，含 `FrmType`/NID/`SRC`/`DST`/方向/`meter_addrs`/分钟
`freeze_time`/`response_result` 与 `ref`）；L3 用 `?ref=listener:<index_id>:<frame_id>`
回传完整帧 JSON（`raw_hex`/`summary`/`parse_error`/`analysis`），**只认同 job 的 ref**
（无关 ref 403、格式错 422、>10 个 422）。

v2 写任务统一携带 `client_request_id`；`cleanup=owned_only` 只允许清理由本任务创建的资源，
不会关闭人工或 UI 复用的会话。烧录仍复用既有控制逻辑，并继续受 `firmware_roots` 白名单和
不可取消约束保护。

### 1.2 v1 专家兼容说明

本文第 2—15 节保留 `/api/ai/v1` 的细粒度操作手册。需要逐步控制串口、直接读取
operation/Artifact、侦听台深链帧、或维护旧客户端时才使用 v1；新 AI 工作流默认从 v2
开始。v1 路径、scope、错误码和 admin grant 语义不因 v2 增加而删除或改名。

## 2. 前置：启动与配置

1. 启动 workbench（`启动工具.bat` 菜单 6，或 `apps/workbench/启动工作台.bat`），默认端口 8790。
2. **配置人工授权管理密钥（可选但推荐）**：启动前设环境变量，否则 admin 授权接口返回 `503 未配置人工授权管理密钥`：

   ```bat
   :: 在 apps/workbench/启动工作台.bat 顶部加，或启动前 set
   set "WORKBENCH_AI_ADMIN_KEY=your-secret"
   ```

   > 当前项目仓库未内置该密钥（安全考虑），首次使用需自行设置并**妥善保管**。日常人工点页面不需要它，只有「AI 自动拿授权」才需要。

## 3. 授权流程（先拿 token，再调能力）

### 3.1 管理员发授权

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/admin/grants \
  -H "X-Workbench-Admin-Key: your-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "scopes": ["module_session:ensure","module_flash:execute","observation:create","evidence:read"],
    "resources": ["cco-main","sta-main"],
    "ttl_seconds": 3600,
    "firmware_roots": ["D:/firmware"],
    "reason": "AI 烧录验证"
  }'
```

返回：

```json
{ "grant": { "grant_id": "grant-...", "scopes": [...], "resources": [...], "expires_at": "...", "firmware_roots": [...] }, "token": "xxxx" }
```

`token` 只在创建时返回一次，之后只存 SHA-256 摘要。授权管理仅限本机（127.0.0.1）。

### 3.2 scope 一览

| scope | 用途 | 所需资源 |
|---|---|---|
| `status:read` | 查整体状态 / 审计 | `*` 或资源 |
| `module_session:ensure` | 确保/创建模块串口会话 | mapping_id |
| `module_session:stop` | 停止模块会话 | 会话 |
| `module_send:execute` | 向模块会话发送指令 | 会话 |
| `module_flash:execute` | 烧录固件 | 会话 |
| `listener:ensure` | 确保侦听台在线 | mapping_id |
| `listener:stop` | 停止侦听台 | 当前侦听台 mapping_id（在线）/ `listener-main`（离线回退） |
| `observation:create` | 创建观察任务 | mapping_id / 会话 |
| `evidence:read` | 读 operation / Artifact / 帧索引 | 对应资源 |
| `listener:trace` | 创建侦听台通信流追踪（回放/live） | 当前侦听台 mapping_id / `listener-main` |
| `simcon:verify` | 运行模拟集中器验证任务 | `simcon` |
| `simcon:send` | 模拟集中器单步下发 / 开关会话 | `simcon` |
| `simcon:read` | 查询模拟集中器会话帧日志 | `simcon` |

### 3.3 资源（resource）说明

- 串口类资源用 `serial_ports.json` 里的 `mapping_id`：`cco-main`、`sta-main`、`listener`（Windows 实际 COM 号见该文件，随接线变化，调用方应优先用 mapping_id 而非硬编码 COM 号）。**模拟集中器（simcon）无固定映射**：verify/step/open 不传 `port` 时自动选择可用串口（排除侦听台/模块日志已映射端口，缺省参数 9600/E/8/1），需要固定端口时显式传 `port`。
- 会话资源为对应 `session_id`（`ms-xxxx`），AI 接口内部会把 session_id 归一到其 mapping_id。
- `resources: ["*"]` 表示全放行（谨慎）。
- 越权访问返回 `403`；token 无效/过期/撤销返回 `401`。

### 3.4 授权管理辅助接口

- `GET  /api/ai/v1/admin/grants` — 列出授权（admin key）
- `POST /api/ai/v1/admin/grants/{grant_id}/revoke` — 撤销授权（admin key）
- `GET  /api/ai/v1/audit` — 审计流水（按授权资源过滤）

## 4. 模块日志串口：会话生命周期

### 4.1 确保会话（幂等）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/ensure \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"mapping_id":"cco-main","module":"cco"}'
```

- 已存在则复用，不存在则创建并打开串口；串口占用冲突返回 `409`；串口不可用返回 `503`。

### 4.2 停止会话

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/{session_id}/stop \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"force": false}'
```

### 4.3 发送指令

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/{session_id}/send \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"data_hex":"68 00 00 ...", "client_request_id":"req-001"}'
```

## 5. 烧录固件（异步 operation）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/flash-operations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"session_id":"ms-xxxx","bin_path":"D:/firmware/app.bin","slot":0,
       "client_request_id":"flash-001"}'
```

- 返回 `202` + `operation_id`；`bin_path` 必须在授权 `firmware_roots` 内，否则 `403`。
- 轮询结果：`GET /api/ai/v1/operations/{operation_id}/wait?timeout_seconds=30`
- 终态：`succeeded`（含 flash 结果）/ `error` / `timed_out`。

## 6. 观察任务（异步 operation）——AI 的核心验证能力

观察 = 「盯住某个数据源，等一条符合条件的内容出现，然后取证」。

### 6.1 module_log 实时日志观察

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/observations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "source": "module_log",
    "target": {"session_id": "ms-xxxx"},
    "window": {"mode":"live", "start":"now", "timeout_seconds": 180},
    "match": {"kind":"literal", "value":"发送成功", "case_sensitive": false},
    "context": {"before": 20, "after": 30},
    "client_request_id": "obs-001"
  }'
```

> 幂等 ID 也可用请求头 `Idempotency-Key` 传，`client_request_id` 缺省时取它；同一 ID 重复提交会复用原操作，内容不一致返回 `409`。

### 6.2 侦听台帧索引观察

`match` **必填**（缺省返回 422），kind 仅 `parsed_frame` / `frame_query`：

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/observations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "source": "listener",
    "target": {"mapping_id": "listener", "capture": "current"},
    "window": {"mode": "live", "timeout_seconds": 180},
    "match": {"kind": "parsed_frame", "frame_kind": "central_beacon", "selector": "first"},
    "client_request_id": "obs-002"
  }'
```

### 6.3 观察任务规则（当前版本）

| 字段 | 约束 |
|---|---|
| `source` | 仅 `module_log` 或 `listener` |
| `match`（module_log） | 叶子：`literal`（非空、≤512 字符）/ `regex`（≤256 字符）/ `loghook_rule`（`rule_id` 须适用于该模块）；复合：`sequence`（1–16 个叶子 + `max_interval_ms` 1–3600000）、`not_seen`（包装一个叶子，窗口内未出现即成功） |
| `match`（listener） | kind 仅 `parsed_frame` / `frame_query`，**必填**；过滤靠 `frame_kind`（当前仅 `central_beacon`，留空=任意）、`where`（数组，`{"path":"analysis.full.<字段>","op":"eq","value":...}`）、`selector`（`first`/`last`/`all`/`first_per_minute`/`nth`） |
| `window.mode` | `live`（只盯创建之后的新内容，`timeout_seconds` 1–3600）/ `time_range`（`start`/`end`，module_log 用 ISO 8601 且须落在内存日志边界内，listener 用 HH:MM:SS）/ `cursor_range`（module_log 给 `start_seq`/`end_seq`，跨度 ≤10000 行；listener 给 `index_id` + `start_frame_id`/`end_frame_id`，跨度 ≤500 帧） |
| `context.before/after` | 0–100，命中时取前后若干行做证据（module_log） |

命中后 operation 进入 `matched` 终态，`result` 含：

```json
{
  "source": "module_log", "session_id": "ms-xxxx", "matched_at": "...",
  "log": { "artifact_id": "art-...", "path": "...", "line_start": 10, "line_end": 12, "match_lines": [11] },
  "snippet": [ ... 命中上下文行 ... ]
}
```

## 7. 查询结果与证据

- `GET /api/ai/v1/operations/{operation_id}` — 单查（waiting 会自动推进一次）
- `GET /api/ai/v1/operations/{operation_id}/wait?timeout_seconds=30` — 阻塞等待到终态（最长 30s/次，可循环）
- `POST /api/ai/v1/operations/{operation_id}/cancel` — 取消观察（烧录不能取消）
- `GET /api/ai/v1/artifacts/{artifact_id}` — Artifact 元数据
- `GET /api/ai/v1/artifacts/{artifact_id}/content` — Artifact 内容（证据正文）

operation 状态机：

```
created → waiting → matched / succeeded
                   → timed_out / cancelled / error / source_stopped / interrupted
```

> `interrupted`：服务重启时未完成的操作自动标记（持久化到 `runtime/ai-control/operations.json`）。

## 8. 侦听台：控制与查询已解析帧

> 解析后端说明（REQS-0019）：侦听台深度解析按三档降级——`local`（WSL 本机
> net8.0 DLL）/ `remote`（委托 Windows 解析服务 `172.25.0.1:8700`）/ `none`
> （无解析后端）。`GET /api/version` 的 `parse_backend` 字段指示当前档位；
> `none` 时深度解析不可用（帧仍采集入库），`/api/parse` 返回 503。

### 8.1 控制

```bash
# 确保侦听台在线（打开串口开始采集）
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/ensure \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"mapping_id":"listener"}'

# 停止侦听台
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/stop \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"force": false}'
```

### 8.2 查询已解析帧

- `GET /api/ai/v1/listener/schema` — 帧种类 / 选择器 / 过滤说明
- `GET /api/ai/v1/listener/indexes` — 索引列表
- `GET /api/ai/v1/listener/indexes/{index_id}/frames` — 帧分页，参数：`offset`、`limit`（1–500）、`query`（关键字）、`nid`、`start_time`/`end_time`（HH:MM:SS 或 HH:MM:SS.mmm）、`after_id`（游标翻页）
- `GET /api/ai/v1/listener/indexes/{index_id}/frames/{frame_id}` — 单帧详情

```bash
curl "http://127.0.0.1:8790/api/ai/v1/listener/indexes" \
  -H "Authorization: Bearer <token>"
```

### 8.3 通信流追踪（发送→响应→接收三段证据链，需求 0009）

以「一次发送的特征」锁定通信流，自动判定 S1 发出（下行帧捕获）/ S2a ACK（链路确认）/
S2b 响应（同报文序号上行）/ S3 接收（0x0020 显式或簇内无重传推断），输出「断在哪一跳」。
对账单位 = 应用层表地址；flow（单流）/ round（时间簇）/ campaign（多轮聚合）三粒度。

```bash
# 回放：给特征+时间窗，异步 operation 返回完整报告
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/traces \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"scope":"round","window":{"mode":"time_range","start_time":"10:00:00","end_time":"10:10:00"},"feature":{"app_id":"0003","frm_type":"终端主动并发抄表"}}'
# → 202 + operation_id → GET /operations/{id}/wait → result.report

# live：注册追踪句柄，只匹配注册之后入库的帧，快照持续更新
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/traces \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"scope":"round","window":{"mode":"live"},"feature":{"app_id":"0003"}}'
# → 202 + wait → result.mode=live，result.trace.trace_id 供后续读取

# 读 live 追踪当前快照（evidence:read）
curl http://127.0.0.1:8790/api/ai/v1/listener/traces/{trace_id} \
  -H "Authorization: Bearer <token>"

# 列出 live 句柄
curl http://127.0.0.1:8790/api/ai/v1/listener/traces \
  -H "Authorization: Bearer <token>"
```

**特征 JSON**（`feature` 字段留空=通配）：`app_id`（必填，如 `0003`）、`msg_seq`（报文序号，
十六进制，flow 粒度必填；留空即聚合全部序号）、`frm_type`、`dst_tei`（对端 TEI）、
`app_raw_contains`（载荷 hex 片段）、`nid`、`channel`。`response_policy` 可选：
`cluster_gap_seconds`（空闲切簇阈值，缺省 60s）、`expect_meters`（显式目标名单）、
`use_ack_evidence` / `confirm_via_0x0020`（缺省 true）、`timeout_ms`。

**报告结构**：`summary`（rounds/meters/full_chain/no_ack/no_response/denied/no_confirm）+
`rounds[]`（时间簇 → `flows[]` 状态机链 `sent→acked→responded→confirmed/denied/timeout`，
每阶段挂 `frame_id` 可用上文帧详情钻取；`meter_table` 按表地址 ok/denied/missing 三分类）+
`proxy_graph`（表地址→应答 STA 代理观测）+ `bad_frames`（坏帧单独计数，不参与判定）。
单帧详情 `frames/{id}` 带 `feature_hint`（可反推的特征草稿，调整后即可 POST /traces）。

## 9. 模拟集中器：验证任务 / 单步下发 / 帧日志

模拟集中器经 AI 控制面暴露在 `/api/ai/v1/simcon/*`，resource 固定为 `simcon`；
串口独占规则与其余接口一致（被占用返回 `409`）。所有收发的 1376.2 帧都会
记录进**会话帧日志**并逐行持久化到 `data/logs/simcon/sc-<时间戳>-<端口>.jsonl`。

### 9.1 运行验证任务（异步 operation）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/verify \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"id":"t1","profile":"anhui",
       "steps":[{"name":"s1","send":{"afn":"00","fn":1,"params":{}}}],
       "client_request_id":"v-001"}'
```

- 返回 `202` + `operation_id`；`GET /operations/{id}/wait?timeout_seconds=30` 到
  `succeeded`，`result` 含 steps 判定、summary、`run_id` 与 `frames_seq`（本次运行的帧 seq 区间）。
- `send` 只写 `afn/fn + params`（ADR-5 语义化，`raw` 传入即报错）；全局信息由
  profile 提供（`apps/workbench/scenarios/profiles/*.json`）。
- 同一会话同一时刻只允许一个验证任务（并发 `409`）；任务不可取消（同烧录）。

### 9.2 单步下发 / 感知主动上报

```bash
# 下发一帧（串口未开时自动选择可用串口打开）
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/step \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"send":{"afn":"06","fn":"F230","params":{}},"profile":"anhui","client_request_id":"s-001"}'

# 只等一帧：感知 CCO 主动上报（30 秒内等到 06H-F230 上行即成功）
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/step \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"recv_only":true,"expect":{"afn":6,"fn":230},"expect_timeout":30}'
```

- `send` 与 `recv_only` 二选一；`expect` / `expect_no_reply` 语义与验证任务 step 一致。
- 支持 `client_request_id` 幂等（重复提交复用原操作，内容不一致 `409`）。

### 9.3 会话帧日志查询（本次运行发了什么 / CCO 上报了什么）

```bash
# 本次运行下发过什么帧（run_id 来自 verify/step 响应）
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?run_id=<run_id>&direction=tx" \
  -H "Authorization: Bearer <token>"

# CCO 主动上报过什么帧（updown=up 即上行帧）
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?updown=up" \
  -H "Authorization: Bearer <token>"

# 有没有某类 afn 的上行帧
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?updown=up&afn=06" \
  -H "Authorization: Bearer <token>"
```

- 过滤参数：`direction`(tx/rx)、`updown`(up/down)、`afn`、`fn`、
  `kind`(step_send/manual_send/auto_reply)、`run_id`、`session_id`、
  `after_seq`+`limit`（游标翻页，limit ≤500）。
- 命中后每帧条目含 `frame_hex`、`afn`、`fn`、`updown`、`parsed`（解析结果）。
- 响应信封：`{session_id, entries[], next_after_seq, matched_total, has_more, counts{tx,rx,uplink}}`
  —— 帧列表在 **`entries`** 键（不是 `frames`，前端曾因读错键卡"加载中"），翻页传 `after_seq=next_after_seq`。
- `GET /api/ai/v1/simcon/session` 查当前/最近会话（session_id、分向计数、日志文件相对路径）。

### 9.4 会话管理

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/open \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{}'
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/close \
  -H "Authorization: Bearer <token>"
```

单步下发会自动开会话；显式 `close` 释放串口（会话日志保留可查，最近 10 个会话）。

### 9.5 语义构帧预览与内置应答（无鉴权辅助端点）

```bash
# 语义化构帧：只经 scenario_codec 算字节，不触串口——下发前预检报文用
curl -X POST http://127.0.0.1:8790/api/simcon/build -H "Content-Type: application/json" \
  -d '{"afn":"06","fn":"F230","params":{},"direction":"down","profile":"anhui","seq":1}'
# → 200 {"hex":"68 ...","length":N}；构帧失败 422

# 当前生效应答规则（内置+覆盖）
curl http://127.0.0.1:8790/api/simcon/responders
```

这两个端点在 simcon 命名空间（`/api/simcon/*`），**不经 /api/ai/v1、无 Bearer 鉴权**。

## 10. 协议字典查询（无鉴权）

```bash
curl http://127.0.0.1:8790/api/dict                    # 四本字典清单（id/名称/条数/来源路径）
curl "http://127.0.0.1:8790/api/dict/oad?q=电压"       # 698.45 OAD
curl "http://127.0.0.1:8790/api/dict/di?q=..."         # 645-2007 DI
curl "http://127.0.0.1:8790/api/dict/afn-fn?q=F230"    # 1376.2 AFN/Fn 语义
curl "http://127.0.0.1:8790/api/dict/rules?q=..."      # loghooks 事件规则
```

- `?q=` 模糊过滤（对条目 JSON 全文做小写包含匹配）。
- 典型用途：查 OAD/DI/Fn 语义支撑验证结论；**observation 的 `loghook_rule.rule_id` 从 `/api/dict/rules` 查**。
- 数据直接来自 `libs/parser_lib/adapters/*/metadata/*.json` 与 `libs/loghooks/rules/`，改 JSON 即生效（无拷贝层）。

## 11. 验证编排 REST（无鉴权，可选）

```bash
curl http://127.0.0.1:8790/api/scenarios               # 场景模板清单
curl http://127.0.0.1:8790/api/scenarios/<id>/task     # 场景激励任务原始 JSON
curl -X POST http://127.0.0.1:8790/api/run \
  -H "Content-Type: application/json" -d '<RunRequest，字段见 apps/workbench/orchestration/dto.py>'
# → 立即返回 run 视图（status=running），轮询 GET /api/run/<run_id> 到终态
#   passed / failed / cancelled / error / inconclusive
# 报告 GET /api/run/<id>/report；产物 GET /api/run/<id>/artifacts[/{artifact_id}]；取消 POST /api/run/<id>/cancel
```

- 与 AI 控制面的取舍：要**授权审计/证据链/幂等**走 `/api/ai/v1`；只是**直接驱动一次全链路验证拿报告**，`/api/run` 更短（无 token、无 operation）。

## 12. 整体状态

```bash
curl http://127.0.0.1:8790/api/ai/v1/status -H "Authorization: Bearer <token>"
```

返回 workbench / listener / module_sessions / 活跃 operations / 串口句柄快照。

## 13. v1 专家调用流程（兼容 checklist）

1. `POST /admin/grants` 拿 token（人来做，一次性）。
2. `GET /status` 确认后端就绪、串口在线。
3. `POST /module-sessions/ensure` 确保模块会话。
4. `POST /flash-operations` 烧录 → `wait` 到 `succeeded`。
5. `POST /observations` 建观察（等日志/帧证据）→ `wait` 到 `matched`。
6. `GET /artifacts/{id}/content` 取证据正文，用于你的验证结论。
7. 模拟集中器侧：`POST /simcon/verify` 跑用例、`POST /simcon/step` 单步下发/等上报、
   `GET /simcon/frames` 查本次运行的帧（见第 9 节）。
8. 侦听台侧：`POST /listener/traces` 追踪一轮抄表的三段证据链（回放历史或 live 盯新帧，
   见 8.3 节）；帧详情的 `feature_hint` 可直接作特征草稿。
9. 需要时 `POST /module-sessions/{id}/stop`、`POST /listener/stop`、`POST /simcon/close` 收尾。
10. （可选）辅助面：`POST /api/simcon/build` 预检构帧、`/api/dict/*` 查协议语义与 loghook 规则 id、
    `/api/run` 直接跑场景（见 9.5、第 10、11 节）。

## 14. 常见错误码速查

| 状态码 | 含义 |
|---|---|
| 401 | 缺 token / token 无效或过期 / 已撤销 |
| 403 | scope 或 resource 越权 / 固件路径不在授权目录 |
| 404 | 会话 / operation / Artifact / 索引不存在 |
| 409 | 串口被占用 / 会话冲突 |
| 422 | 请求体校验失败（如 match 非法、超时越界） |
| 503 | 后端服务不可用（串口未启用 / 侦听台不可用 / 未配置 admin key） |

## 15. 与页面操作的关系

- AI 控制面复用与页面**同一套后端服务**（`ModuleSerialService` / listener service），串口同一时刻独占，页面与 AI 不能同时开同一串口。
- 前端 bug 已由 ADR-27 修复（`ms-refresh-speed` 缺失元素导致实时日志页启动无反应），本指南 API 不受影响。
