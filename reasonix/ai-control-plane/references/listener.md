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

## 分钟采集分析分桶口径（缺报判定必读）

「分钟采集分析」页面的统计口径与真实采集**可能不一致**，缺报判定前必须先还原页面口径。

- **页面分桶键**：`apps/listener/log_service.py` 的 `list_task_minute_periods` 按
  `time_seconds % period_ms` 分桶，即 **`minute_reports.time_seconds`（上报时刻）**对齐到周期窗口。
- **权威归属**：`minute_reports.freeze_time`（冻结时刻）才是该周期真正采集到的归属。
- **口径陷阱**：存在**迟报 / 补采**时（如上报时刻比冻结晚 1~2 分钟），两者分桶结果不一致——
  页面会显示「假缺报」（其实冻结周期采集完整）。
- **判定**：真实缺报一律以 `freeze_time` 为准；页面显示"去重后 STA 数 / 缺报"需结合两者，
  并交叉 CCO 日志（发送侧）与侦听台索引（接收侧）验证（见 `offline-analysis.md` 第 6 节）。

```bash
# 某冻结周期实到 STA（权威）：缺谁一目了然
# freeze_time 存解析字段"冻结时刻"的 value，格式 YYYY-MM-DD HH:MM:SS；用 LIKE 前缀匹配该分钟
sqlite3 .build_plain/apps/listener/runtime/indexes/idx-*.sqlite3 \
  "SELECT station_key, freeze_time, report_count FROM minute_reports WHERE freeze_time LIKE '2026-08-31 14:22%';"

# 与页面同口径：按上报时刻分桶（会混入迟报，产生假缺报）
# ⚠ time_seconds 实际是毫秒（列名误导）；period_ms = 分钟数×60000，2 分钟周期 = 120000
sqlite3 .build_plain/apps/listener/runtime/indexes/idx-*.sqlite3 \
  "SELECT time_seconds/120000 AS bucket_2min, COUNT(DISTINCT station_key) AS sta_cnt
   FROM minute_reports GROUP BY bucket_2min;"
```

## 分钟采集分桶查询接口（REQS-0018，scope=evidence:read，API 优先）

> 与页面**同一方法**（`list_task_minute_periods`），口径零分叉；缺报判定走它，
> 不必手写 SQL。缺服务 503、非法参数 422。

```bash
curl "http://127.0.0.1:8790/api/ai/v1/listener/minute-periods?task_no=1&cco_tei=001" \
  -H "Authorization: Bearer <token>"
# 可选：period_minutes（1–1440）、nid、start_time/end_time（HH:MM:SS）
```

- 响应 `{"periods":[{period_start, period_end, report_count, reports[]}]}`；
  每 report 含 `freeze_time` / `freeze_ok` / `response_result` —— 权威口径直接可用。

## 解析后端（local / remote / none，REQS-0019）

侦听台深度解析按三档降级：

- `local`：WSL 本机 net8.0 DLL 解析；
- `remote`：委托 **Windows 解析网关**（`172.25.0.1:8700`，net48 DLL）；
- `none`：无解析后端——帧照常采集入库 / 可查，但**深度解析字段不可用**。

- **查档位**：`GET http://127.0.0.1:8765/api/version` → `parse_backend`（及 `dll_available`）。
- `none` 时 `/api/parse`（8765）返回 503，不影响串口采集与日志索引。
- **起网关**（Windows 侧，需人在 Windows 执行）：桌面 `wsl环境部署.bat` → [4] 启动 / [5] 停止；
  或 `powershell -File uart-map.ps1 -Action start-gateway`（详见 `tools/scripts/README.md`）。
- **排查提示**：帧缺协议明细时先看 `parse_backend`；`none` → 先起网关再继续，别怀疑数据/链路。
