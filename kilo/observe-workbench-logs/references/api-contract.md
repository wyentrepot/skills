# observe-workbench-logs — API 契约

> 运行时事实来源：ZZT_SELF 工程的 `/01-workfile-ai/01-zzt/ZZT_SELF/docs/16-AI操作指南.md` 与
> `docs/16-AI操作指南.md`；P2 客户端边界见 `docs/03-骨架设计.md §6.3` 与
> `docs/04-任务安排.md P2`。本文件是客户端与 `/api/ai/v1` 的交互契约，
> 避免 SKILL.md 过长。

## 1. 全局约定

- Base URL：`http://127.0.0.1:8790`（默认）；仅允许规范化本机工作台地址，**拒绝 URL userinfo**。
- 请求头：`Authorization: Bearer <token>`；`Content-Type: application/json`。
- Token 唯一来源：环境变量 `WORKBENCH_AI_TOKEN`。不出现于 CLI 参数、配置文件、
  输出、异常文本或 URL userinfo。
- 默认 dry-run：只输出规范化、脱敏的 JSON 计划（`execute:false`），零 HTTP、零 operation。
  仅显式 `--execute` 发请求。
- 客户端是硬件非侵入观察：不提供 `ensure/start/stop/send/flash/烧录/串口打开/文件扫描/cancel`。

## 2. 六命令 → 端点

| 命令 | 方法 + 路径 | 只读/写入 | 说明 |
|---|---|---|---|
| `status` | `GET /api/ai/v1/status` | 只读 | 工作台/会话/观察任务状态 |
| `observe` | `POST /api/ai/v1/observations` | 写入 operation/audit | 对既有 module session 或 listener index 创建有界观察，不控制硬件 |
| `wait` | `GET /api/ai/v1/operations/{operation_id}/wait?timeout_seconds=N` | 只读 | 有界轮询到终态；单次 N≤30；不发 cancel |
| `artifact` | `GET /api/ai/v1/artifacts/{artifact_id}` | 只读 | 读服务端登记 Artifact 的 manifest |
| `listener-schema` | `GET /api/ai/v1/listener/schema` | 只读 | 帧语义与字段选择器 |
| `frame-detail` | `GET /api/ai/v1/listener/indexes/{index_id}/frames/{frame_id}` | 只读 | 复合 `index_id + frame_id` 深链读帧 |

## 3. observe 请求 shape

```json
{
  "source": "module_log",
  "target": {"session_id": "ms-1234"},
  "window": {"mode": "live", "start": "now", "timeout_seconds": 120},
  "match": {"kind": "literal", "value": "central beacon first-of-minute flag=1"},
  "context": {"before": 20, "after": 30},
  "lifecycle": {"ensure_source_running": false, "on_finish": "leave_running"}
}
```

- `source`：`module_log` 或 `listener`。
  - `module_log` target 必须 `session_id`（既有后端会话）。
  - `listener` target 必须 `index_id`（既有索引），`mapping_id` 默认 `listener-main`。
- `window.mode`：`live`（`start:"now"` + `timeout_seconds`）、`cursor_range`
  （`start_seq`/`end_seq` 闭区间，module 日志 seq）。
- module `match.kind`：`literal` / `regex` / `loghook_rule` / `sequence` / `not_seen`；`value` 为文本或 rule_id。
- listener `match.kind`：`parsed_frame` / `frame_query`，必须有 `frame_kind`，可选 selector。
- `lifecycle.ensure_source_running`：本客户端固定 `false`（不启动串口来源）。

## 4. operation 状态

```text
created -> waiting -> matched
                  -> timed_out
                  -> cancelled
                  -> error
```

终态：`matched / timed_out / cancelled / error / interrupted / source_stopped`。
非终态（`created/waiting`）可继续 wait。客户端到终态即停止，不 cancel。

## 5. 命中结果与证据

- module `matched` 结果含 `log.artifact_id`（逻辑 Artifact ID）、命中行、行区间与下载 URL。
- listener `matched` 结果含复合 `index_id + frame_id` 及 detail/UI 深链。
- `artifact` 返回服务端登记的逻辑 Artifact ID 的 manifest；`/content` 可取内容。
- `frame-detail` 保留 `index_id + frame_id` 复合键，返回解析 JSON。

## 6. 错误码

| HTTP | 含义 | 客户端行为 |
|---|---|---|
| 401 | 缺/无效 Bearer token | 安全失败，提示设 `WORKBENCH_AI_TOKEN` |
| 403 | scope/resource 越权 | 安全失败，不扩大权限 |
| 404 | 会话/索引/Artifact 不存在 | 安全失败（`KeyError` → 404） |
| 409 | 资源冲突/幂等冲突 | 安全失败 |
| 422 | 非法观察参数 | 安全失败，显示校验详情 |
| 503 | 后端/来源不可用 | 安全失败 |

所有失败：脱敏错误 + 非零退出码，绝不回显 Token，不自动重试破坏性操作。

## 7. 禁止能力清单

`ensure`、`start`、`stop`、`send`、`flash`、烧录、串口打开、`cancel`、
任意文件系统路径读取/扫描/上传、operation cancel、root/任意路径参数。
