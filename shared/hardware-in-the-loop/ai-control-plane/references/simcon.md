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
  -d '{"recv_only":true,"expect":{"afn":"06","fn":"F230"},"expect_timeout":30}'
```

- **expect 记法（AFN/Fn，REQS-0036）**：`afn` 用 2 位 hex **字符串**（协议记法 10H 写
  `"10"`；数值按原始字节值 0x10=16，直接写 `10` = 0x0A 会静默不匹配）；`fn` 写
  `"F230"` / `"F2"` / 十进制均可。超时原因透出逐帧不匹配差异（如
  `AFN 不匹配: 期望0x0A, 实际0x10`），据此自纠。

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

## 并发抄表 / 档案 / recipes（REQS-0027/0028/0030，无 Bearer 直连面）

> 这组在 `/api/simcon/*` 命名空间（不经 /api/ai/v1、无 token）；契约细节见
> `references/api-contract.md` §5。

```bash
# 并发抄表滑窗任务（10H-F2 档案 + 14H-F1 下发；回快照）
curl -X POST http://127.0.0.1:8790/api/simcon/batch_read \
  -H "Content-Type: application/json" \
  -d '{"meters":["999999999999","020103040506"],"max_concurrent":5,"mode":"batch","protocol_type":2}'
# 任务快照：{job_id, meters_total, max_concurrent, in_flight, queued, done,
#            success, failed, deny_breakdown, finished, rows[]}
curl http://127.0.0.1:8790/api/simcon/batch_read/<job_id>      # 单任务快照
curl -X POST http://127.0.0.1:8790/api/simcon/batch_read/<job_id>/stop   # 停止

# 常用任务一键 recipe（清空/添加档案等；参数见 GET /recipes）
curl http://127.0.0.1:8790/api/simcon/recipes
curl -X POST http://127.0.0.1:8790/api/simcon/recipes/add_archive/run \
  -H "Content-Type: application/json" -d '{"overrides":{}}'

# 档案 / 在网查询（10H-F2 / 10H-F1 实时下发）
curl "http://127.0.0.1:8790/api/simcon/archive/query?start=0&count=200"
curl http://127.0.0.1:8790/api/simcon/online

# 统计面：主动上报分桶（06H F1-F5+停复电）与并发抄表周期统计
curl http://127.0.0.1:8790/api/simcon/report_buckets
curl "http://127.0.0.1:8790/api/simcon/batch/stats?period=15m"
```
