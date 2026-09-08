# 模拟集中器：验证任务 / 单步 / 帧日志

> **无固定串口映射**：verify/step/open 不传 `port` 时自动选择可用串口（排除侦听台/
> 模块日志已映射端口，缺省 9600/E/8/1），需要固定端口时显式传 `port`。
> resource 固定 `simcon`；所有收发的 1376.2 帧都会进**会话帧日志**并持久化到
> `data/logs/simcon/sc-*.jsonl`。

## 运行验证任务（异步，不可取消）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/verify \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"id":"t1","profile":"anhui","steps":[{"send":{"afn":"00","fn":1,"params":{}}}],"client_request_id":"v-001"}'
```

- 202 + operation_id → `GET /operations/<id>/wait` 到 succeeded；
  `result` 含 steps/summary/`run_id`/`frames_seq`（本次运行的帧 seq 区间）。
- `send` 只写 `afn/fn + params`（ADR-5，传 `raw` 报错）；profile 在
  `apps/workbench/scenarios/profiles/`。
- 并发 verify 返回 409。

## 单步下发 / 感知主动上报（同步）

```bash
# 下发指定 afn/fn（串口未开时自动按可用串口打开）
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/step \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"send":{"afn":"06","fn":"F230","params":{}},"client_request_id":"s-001"}'

# 只等一帧：感知 CCO 主动上报
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/step \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"recv_only":true,"expect":{"afn":6,"fn":230},"expect_timeout":30}'
```

## 查询本次运行的帧

```bash
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?run_id=<run_id>&direction=tx" \
  -H "Authorization: Bearer <token>"
# CCO 主动上报过什么帧 / 有无某类 afn 上行帧
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?updown=up&afn=06" \
  -H "Authorization: Bearer <token>"
```

- 过滤：`direction`(tx/rx)、`updown`(up/down)、`afn`、`fn`、
  `kind`(step_send/manual_send/auto_reply)、`run_id`、`session_id`、
  `after_seq`+`limit`(≤500) 游标翻页；每帧含 `frame_hex`/`parsed` 解析结果。
- **响应信封 `{session_id, entries[], next_after_seq, matched_total, has_more, counts{tx,rx,uplink}}`**
  —— 帧列表在 `entries` 键（不是 `frames`），翻页传 `after_seq=next_after_seq`。

## 会话管理

- `GET /api/ai/v1/simcon/session`：当前/最近会话信息。
- `POST /api/ai/v1/simcon/open`（body 可省略，自动选串口）、`POST /api/ai/v1/simcon/close`：
  显式管理；close 释放串口，日志保留可查。

## 1376.2 收发库只读查询（REQS-0018，scope=simcon:read）

> 持久化库 `data/listener_13762.sqlite`（frame_log/report_event/query_snapshot）的结构化查询。
> 全部只读 GET；库未启用返回 503。

```bash
# 06H 主动上报事件历史（report_event）
curl "http://127.0.0.1:8790/api/ai/v1/simcon/store/events?limit=50" \
  -H "Authorization: Bearer <token>"

# 下发查询快照列表（query_snapshot，可 afn/fn 过滤）
curl "http://127.0.0.1:8790/api/ai/v1/simcon/store/snapshots?afn=10&fn=F2&limit=20" \
  -H "Authorization: Bearer <token>"

# 快照明细行（query_snapshot_item；不存在的快照返回空 items）
curl "http://127.0.0.1:8790/api/ai/v1/simcon/store/snapshots/1" \
  -H "Authorization: Bearer <token>"
```

- 响应信封 `{"items":[...]}`；用于排查 06H 上报是否落库、下发查询结果快照。
- 与 `/simcon/frames`（会话帧日志 sc-*.jsonl，实时）互补：store 是**持久化库**，
  跨会话保留（按天滚动 5 天），frames 是本次会话的帧序列。
