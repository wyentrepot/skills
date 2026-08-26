---
name: observe-workbench-logs
description: 'Query ZZT_SELF workbench status and bounded log/frame evidence over /api/ai/v1. The skill is hardware-non-invasive: it never opens, starts, stops, sends to, or flashes serial resources; observe only creates an auditable bounded server-side operation against an EXISTING module session or listener index. Explicit invocation only; default dry-run.'
metadata:
  author: reasonix
  version: "1.1.0"
  applies-to: /01-workfile-ai/01-zzt/ZZT_SELF
---

# 侦听台 AI 观察技能（observe-workbench-logs）

项目内、**显式调用**、**默认 dry-run** 的 AI 日志观察技能。底层事实以
`docs/16-AI操作指南.md` 与代码为准；本文件是**执行步骤**，硬件非侵入观察：不碰串口控制，但 `observe` 会创建有界、可审计的服务端 operation。

## 边界（先读）

- 本技能**硬件非侵入**：不提供、不隐藏 `ensure/start/stop/send/flash/烧录/串口打开/文件扫描`；`observe` 是唯一 POST，会创建 operation、audit，命中或结束时可登记 Artifact。
- 只能通过 `$observe-workbench-logs` 显式调用；`allow_implicit_invocation: false`。
- 目标只能是**既有** module session 或**既有** listener index/capture；不新建、不启动来源。
- 默认 dry-run：只输出脱敏计划，零 HTTP、零 operation。只有 `--execute` 才发请求。
- Token 唯一来自环境变量 `WORKBENCH_AI_TOKEN`；不得出现在参数、输出、异常或 URL；客户端会在输出中替换实际环境 Token。
- 单次服务端 wait ≤ 30 秒；终态即停止，绝不发 cancel。

## 前置条件

1. workbench 在 8790 运行（`GET /api/health` → 200）。
2. 已有人工授权并持有 Token，且环境变量 `WORKBENCH_AI_TOKEN` 已设置（最小 scope：
   `status:read`、`observation:create`、`evidence:read`；其中 `observation:create` 会写入审计状态）。
3. 目标串口会话或侦听台索引**已存在**（`status` 可查）。

## 六命令

| 命令 | 端点 | 说明 |
|---|---|---|
| `status` | `GET /api/ai/v1/status` | 查工作台/会话/观察任务状态 |
| `observe` | `POST /api/ai/v1/observations` | 对既有 session/index 创建有界观察 |
| `wait` | `GET /api/ai/v1/operations/{id}/wait` | 有界轮询到终态，不 cancel |
| `artifact` | `GET /api/ai/v1/artifacts/{id}` | 读服务端登记的 Artifact |
| `listener-schema` | `GET /api/ai/v1/listener/schema` | 查侦听台帧语义与字段选择器 |
| `frame-detail` | `GET /api/ai/v1/listener/indexes/{index_id}/frames/{frame_id}` | 复合深链读帧 |

## 第一步：先查状态（只读）

```bash
SKILL_DIR=/home/02-skill-fc/skills/kilo/observe-workbench-logs
cd "$SKILL_DIR/scripts"
python workbench_ai_client.py status            # dry-run：打印计划，零 HTTP
python workbench_ai_client.py status --execute  # 真查状态，需 WORKBENCH_AI_TOKEN
```

- 无 Token 时 `status --execute` 安全失败并提示设置 `WORKBENCH_AI_TOKEN`。
- 输出是稳定 JSON：会话列表、运行状态、活动观察任务。

## 第二步：创建观察（默认 dry-run）

把自然语言转成结构化参数；**关键参数缺失时停止并请求补充**：

```bash
# 默认 dry-run：只打印脱敏计划
python workbench_ai_client.py observe \
  --source module_log --session-id ms-1234 \
  --kind literal --value "central beacon first-of-minute flag=1" \
  --mode live --timeout-seconds 120

# 确认无误后 --execute 才真正 POST
python workbench_ai_client.py observe \
  --source module_log --session-id ms-1234 \
  --kind literal --value "central beacon first-of-minute flag=1" \
  --mode live --timeout-seconds 120 --client-request-id obs-cco-beacon-001 --execute
```

侦听台必须使用帧契约，而不是模块日志文本匹配器：

```bash
python workbench_ai_client.py observe \
  --source listener --index-id idx-7 \
  --kind frame_query --frame-kind central_beacon \
  --selector first_per_minute --timeout-seconds 120 --execute
```

- `--source module_log` 必须给 `--session-id`；匹配器为 `literal` / `regex` / `loghook_rule` / `sequence` / `not_seen`，使用 `--value`。
- `--source listener` 必须给 `--index-id`，且必须使用 `--kind parsed_frame` 或 `frame_query` 与 `--frame-kind`；可用 `--selector first|last|all|first_per_minute|nth`。
- `--mode live` 等新数据；module `cursor_range` 需要 `--start-seq/--end-seq`，listener `cursor_range` 需要 `--index-id --start-frame-id --end-frame-id`。
- 需要重试同一个 observe 时，首次调用起指定并复用 `--client-request-id`；客户端将它作为 `Idempotency-Key`。不自动重试。
- `lifecycle.ensure_source_running` 固定为 `false`：本技能**不会**帮你启动串口来源。

## 第三步：等待终态

```bash
python workbench_ai_client.py wait --operation-id op-log-xxx --timeout-seconds 30 --execute
```

- 返回 `matched / timed_out / cancelled / error / interrupted / source_stopped` 终态。
- 单次 ≤ 30 秒；非终态（`waiting/created`）可再次 wait，客户端到终态即停，不发 cancel。
- `matched` 时结果含 `log.artifact_id`（module）或复合 `index_id + frame_id`（listener）。

## 第四步：取证据

```bash
python workbench_ai_client.py artifact --artifact-id op-log-xxx-raw --execute
python workbench_ai_client.py frame-detail --index-id idx-7 --frame-id 42 --execute
python workbench_ai_client.py listener-schema --execute
```

- `artifact`：只读取服务端登记的 Artifact manifest 与命中位置；本技能不调用 `/content`，不会下载原始日志。
- `frame-detail`：必须保留 `index_id + frame_id` 复合深链，返回解析 JSON 与详情 URL。
- `listener-schema`：可查询的帧字段与语义选择器。

## 错误处理与安全

- 服务端非 2xx、Token 缺失/非法、base URL 含 userinfo、缺 session/index → **安全失败**，
  脱敏错误 + 非零退出码，绝不回显 Token。
- 不自动扩大权限、不强制停止来源、不重试破坏性操作。
- 断线/超时/技能退出均不关闭后端串口（`leave_running`）；服务端既有 observation 依其有界 deadline 结束。
