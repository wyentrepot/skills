# 观察任务语义（先建观察，再制造事件）

> 拆自 wb-base/SKILL.md（2026-11-18 拆薄）。正文 §4 只留红线与窗口速查；建观察任务的完整 match 矩阵与示例读本文件。

### §4.1 观察任务语义（先建观察，再制造事件）

最小链：`POST /api/ai/v1/observations` → `GET /operations/{id}/wait?timeout_seconds=30` → `GET /artifacts/{artifact_id}/content`。**时序是关键**：module_log 观察只盯"创建时刻之后"的新日志——先建观察，再制造目标事件。

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

幂等：`client_request_id` 缺省时取请求头 `Idempotency-Key`。**match 矩阵**（叶子 3 + 复合 2）：

- 叶子：`literal`（value 非空 ≤512 字符，带 `case_sensitive`）、`regex`（≤256 字符）、`loghook_rule`（`rule_id` 须是该模块的 module_log 规则，**从 `GET /api/dict/rules` 查**，无鉴权）。
- 复合：`sequence`（`steps` 叶子×1–16 + `max_interval_ms` 1–3600000，按顺序出现）、`not_seen`（`matcher` 叶子；仅**闭合窗**未出现才判 pass，live 窗到期且无可信到达时间 → `inconclusive`）。

| window.mode | 参数 | 约束 |
| --- | --- | --- |
| `live` | `timeout_seconds` 1–3600 | 只盯创建之后的新事件 |
| `time_range` | ISO 8601 `start`/`end` | 须落在当前内存日志边界内 |
| `cursor_range` | `start_seq`/`end_seq` | 回放既有区间，跨度 ≤10000 行且区间已闭合 |

**侦听台帧观察（source=listener）**：

```bash
-d '{"source":"listener",
     "target":{"mapping_id":"listener","capture":"current"},
     "window":{"mode":"live","timeout_seconds":180},
     "match":{"kind":"parsed_frame","frame_kind":"central_beacon","selector":"first"}}'
```

- `match` **必填**（缺省直接 422），kind 仅 `parsed_frame` / `frame_query`；过滤三件套 `frame_kind`（当前仅 `central_beacon`，留空=任意）、`where`（`{"path":"analysis.full.<字段>","op":"eq","value":...}`，op 目前仅 eq）、`selector`（first/last/all/first_per_minute/nth）。
- `mapping_id` 用 `listener`（不是 `listener-main`）；字段路径先 `GET /api/ai/v1/listener/schema` 确认；window 同样支持 time_range / cursor_range（须给 `index_id` + `start_frame_id`/`end_frame_id`，跨度 ≤500 帧）。

> 来源：ai-control-plane/references/observations.md；ai-control-plane/references/operation-guide.md

