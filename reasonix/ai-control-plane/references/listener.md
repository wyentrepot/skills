# 侦听台：采集控制、帧查询、通信流追踪

## 控制

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/ensure \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"mapping_id":"listener"}'
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/stop \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"force":false}'
```

- `listener:stop` 校验的 resource：在线时为当前 mapping_id（`listener`），离线回退
  `listener-main`；窄授权（`resources` 非 `*`）需两者都包含。

## 帧查询

```bash
curl http://127.0.0.1:8790/api/ai/v1/listener/schema -H "Authorization: Bearer <token>"
curl http://127.0.0.1:8790/api/ai/v1/listener/indexes -H "Authorization: Bearer <token>"
curl "http://127.0.0.1:8790/api/ai/v1/listener/indexes/<index_id>/frames?offset=0&limit=100" \
  -H "Authorization: Bearer <token>"
curl "http://127.0.0.1:8790/api/ai/v1/listener/indexes/<index_id>/frames/<frame_id>" \
  -H "Authorization: Bearer <token>"
```

- 分页参数：`offset`、`limit`（1–500）、`query`（关键字）、`nid`、
  `start_time`/`end_time`（HH:MM:SS 或 HH:MM:SS.mmm）、`after_id`（游标翻页，
  取上一页最后一条 frame_id）。
- 单帧详情响应的 `feature_hint` 就是可反推的特征草稿，改一改即可 POST /traces。

## 通信流追踪（三段证据链：S1 发出 → S2 ACK/响应 → S3 接收）

以「一次发送的特征」追踪一轮业务（如并发抄表 0x0003），输出「断在哪一跳」而非二值 pass/fail。

```bash
# 回放：特征+时间窗 → 202 → wait → result.report（完整报告）
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/traces \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"scope":"round","window":{"mode":"time_range","start_time":"10:00:00","end_time":"10:10:00"},"feature":{"app_id":"0003"}}'

# live：只盯注册之后的新帧 → wait → result.trace.trace_id
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/traces \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"scope":"round","window":{"mode":"live"},"feature":{"app_id":"0003"}}'

# live 快照读取 / 句柄列表（scope evidence:read）
curl http://127.0.0.1:8790/api/ai/v1/listener/traces/<trace_id> -H "Authorization: Bearer <token>"
curl http://127.0.0.1:8790/api/ai/v1/listener/traces -H "Authorization: Bearer <token>"
```

- `feature`：`app_id` 必填（0003 并发抄表 / 0001 单表 / 00A1 / 0020 / 0008）；
  `msg_seq` 留空=聚合；`frm_type`/`dst_tei`/`nid`/`app_raw_contains` 可选。
  scope 粒度：flow（须给 msg_seq）/ round / campaign。
- 报告结构：`summary` + `rounds[]`（时间簇 → `flows[]` 状态机链
  sent→acked→responded→confirmed/denied/timeout，每阶段挂 `frame_id` 可回帧详情钻取；
  `meter_table` 表地址 ok/denied/missing 三分类）+ `proxy_graph` + `bad_frames`（坏帧只计数）。
