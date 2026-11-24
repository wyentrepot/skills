# listener 语义查询（trace_query / minute_periods）

> 拆自 wb-base/SKILL.md（2026-11-18 拆薄）。漏点/通信流追踪任务才读本文件。

### §3.6 listener 语义查询（`trace_query` / `minute_periods`）

listener observation 的 `match.kind` 除 `parsed_frame` / `frame_query` 外，还有两个**复用既有能力、不新建索引**的语义查询：`trace_query` 复用 `TraceService.run_replay`（并发抄表、单表、00A1、0020、0008 的多跳通信流）；`minute_periods` 复用 `list_task_minute_periods`（分钟采集，**禁止通过 raw HEX 猜测**）。

```json
{"source":"listener", "target":{"index_id":"idx-20260630-a"},
 "window":{"mode":"time_range","start":"00:00:00.000","end":"00:05:00.000"},
 "match":{"kind":"trace_query", "scope":"round",
   "feature":{"app_id":"0003","msg_seq":"1EC2","frm_type":"终端主动并发抄表",
              "dst_tei":"087","nid":"00947F69","channel":"载波",
              "app_raw_contains":"123456789012","raw_hex_contains":"123456789012"},
   "directions":["downlink","uplink","ack"]},
 "completion":{"match_count":1}}
```

- `feature`：`app_id` 必填；`scope` 为 `flow`/`round`/`campaign`；`directions` 只做 L2 展示与计数筛选，同一通信流默认保留必要 ACK 和对端帧。
- `raw_hex_contains` 对整帧 `raw_hex` 验证、`app_raw_contains` 对已解析应用载荷验证；前者**仅作末端验证**，删空白后须为偶数长度 2–512 个十六进制字符，**无 `app_id`/NID/时间窗/帧 ID 窗口任一收窄条件时 422**。
- `minute_periods`：`match` 给 `task_no`（必填）/`period_minutes`/`cco_tei`/`nid`，窗口仅 `time_range`；业务归属**以 `freeze_time` 为准**，L2 同时给 `log_time` 与 `freeze_time`，不得用上报时间替代。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

