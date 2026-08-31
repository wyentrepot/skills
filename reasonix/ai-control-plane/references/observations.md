# 观察任务（监控日志 / 盯帧取证）

> 最小链：`POST /api/ai/v1/observations` → `GET /operations/{id}/wait?timeout_seconds=30`
> → `GET /artifacts/{artifact_id}/content`。
> **时序关键：先建观察，再制造目标事件。** module_log 观察只盯「创建时刻之后」的新日志。

## module_log 日志观察

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/observations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "source":"module_log",
    "target":{"session_id":"<session_id>"},
    "window":{"mode":"live","start":"now","timeout_seconds":180},
    "match":{"kind":"literal","value":"<要找的字符串>","case_sensitive":false},
    "context":{"before":20,"after":30},
    "client_request_id":"<id>"
  }'
```

幂等：`client_request_id` 缺省时取请求头 `Idempotency-Key`。

## match 矩阵

叶子三种：

- `{"kind":"literal","value":"非空≤512字符","case_sensitive":bool}`
- `{"kind":"regex","value":"≤256字符"}`
- `{"kind":"loghook_rule","rule_id":"..."}` —— 须为该模块的 module_log 规则，
  **rule_id 从 `GET /api/dict/rules` 查**（无鉴权，见 helpers）

复合两种：

- `{"kind":"sequence","steps":[叶子×1–16],"max_interval_ms":<1–3600000>}`（按顺序出现）
- `{"kind":"not_seen","matcher":<叶子>}`（窗口内**未**出现即成功）

## window 三种

| mode | 参数 | 约束 |
| --- | --- | --- |
| live | `timeout_seconds` 1–3600 | 只盯创建之后的新事件 |
| time_range | ISO 8601 `start`/`end` | 须落在当前内存日志边界内 |
| cursor_range | `start_seq`/`end_seq` | 回放既有区间，跨度 ≤10000 行且区间已闭合 |

## 侦听台帧观察（source=listener）

```bash
-d '{"source":"listener",
     "target":{"mapping_id":"listener","capture":"current"},
     "window":{"mode":"live","timeout_seconds":180},
     "match":{"kind":"parsed_frame","frame_kind":"central_beacon","selector":"first"}}'
```

- `match` **必填**（缺省直接 422），kind 仅 `parsed_frame` / `frame_query`。
- 过滤三件套：`frame_kind`（当前仅 `central_beacon`，留空=任意）、`where`（数组，每项
  `{"path":"analysis.full.<字段>","op":"eq","value":...}`，op 目前仅 eq）、
  `selector`（first / last / all / first_per_minute / nth）。
- `mapping_id` 用 `listener`（不是 listener-main）；字段路径先
  `GET /api/ai/v1/listener/schema` 确认。
- window 同样支持 time_range / cursor_range（须给 `index_id` + `start_frame_id`/`end_frame_id`，
  跨度 ≤500 帧）。

## 轮询与取证

- `wait` 命中 → `state=matched`；`result.snippet` 含命中上下文行，
  `result.log.artifact_id`（`art-xxx`）即证据句柄。
- `GET /artifacts/<artifact_id>/content` 取正文；`GET /artifacts/<artifact_id>` 看元数据。
- 取消：`POST /operations/{id}/cancel`（烧录类不可取消）。
