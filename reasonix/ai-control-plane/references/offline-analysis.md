# 离线数据排查（漏点定位）— 数据源速查

> 用于排查「页面显示缺帧 / 缺报 / 漏点」类问题。**排查走离线直查数据源**，不依赖 HTTP 控制面。
> 完整实战案例见 `使用经验/安徽分钟采集漏点排查.md`；分桶口径见 `listener.md`「分钟采集分析分桶口径」；
> CCO 帧特征见 `cco-log.md`。

## 0. 排查前置：先确认采集链路在线

**任何「某时段缺数据」结论之前，先确认该时段采集链路在线**，否则可能把「链路断线无数据」误判成「漏报/丢帧」。

```bash
# CCO 日志中找「串口会话打开/关闭」事件（发送侧链路状态）
grep -aE "串口会话打开|串口会话关闭|串口关闭" .build_plain/data/logs/模块/cco/*.log
# 若时段内无任何帧（索引库/日志库全空），多半是链路断，不是漏
```

- 典型：11:16:19 串口关闭 → 14:09:36 重开，中间 12:00~14:00 全无数据，是**链路断线**不是缺报。

## 1. 数据源全景（路径以打包布局 `.build_plain/` 为根；开发树去掉前缀，即 `apps/...` / `data/...`）

| 数据源 | 路径 | 存什么 | 排查用途 |
| --- | --- | --- | --- |
| 侦听台索引库 | `.build_plain/apps/listener/runtime/indexes/idx-<时间戳>-<hash>.sqlite3` | `frames` + `minute_reports` | **分钟分析数据源（权威）** |
| 侦听台原始日志 | `.build_plain/data/logs/侦听台/devtty*_*_自动保存.txt` | 7E HPLC 帧原文 | 索引库的原料，回查帧原文 |
| 模拟集中器库 | `.build_plain/data/listener_13762.sqlite` | `frame_log` + `report_event` + `report_meter_data` + `query_snapshot*` | 06F230 主动上报 / 下发查询快照（记录面不全） |
| simcon 会话帧 | `.build_plain/data/logs/simcon/sc-*.jsonl` | 1376.2 帧 JSONL | 会话分段记录（收发双向） |
| CCO 模块日志 | `.build_plain/data/logs/模块/cco/*.log` | 固件运行日志（含 06F230/11e4/11e3 帧 hex） | **发送侧真相**，判定真没发还是发了没抓到 |

> 开发树实际位置（本仓库）：索引库在 `apps/listener/runtime/indexes/`，其余在 `data/` 下，
> 结构同打包布局，只是没有 `.build_plain/` 前缀。

## 2. 侦听台索引库（权威）

```bash
ls .build_plain/apps/listener/runtime/indexes/idx-*.sqlite3   # 按索引（每个采集会话一个）
```

### frames 表（原始帧）

| 列 | 含义 |
| --- | --- |
| `id` / `sequence` / `log_time` | 帧主键 / 序号 / 时间 |
| `raw_hex` / `summary_json` / `parse_error` | 帧原文 / 解析结果 / 解析错误 |
| `nid` / `frm_type` / `app_id` / `msg_seq` | 网络标识 / 帧类型 / 应用标识 / 报文序号 |
| `meter_addrs` / `sta_tei` | 电表地址集合 / STA TEI |
| `flow_dir` / `ack_peer` | 收发方向 / ACK 对端 |

### minute_reports 表（分钟采集分析）

| 列 | 含义 |
| --- | --- |
| `frame_id` / `log_time` / `time_seconds` | 关联帧 / 记录时间 / **上报时刻**（⚠ 列名误导，实际存**绝对毫秒**） |
| `cco_tei` / `station_key` / `source_mac` | CCO TEI / **STA 唯一键（电表标识）** / 源 MAC |
| `task_no` / `protocol_type` / `meter_type` | 任务号 / 协议类型 / 表计类型 |
| `response_result` | 应答结果 |
| `freeze_time` | **冻结时刻（权威归属）**，格式 `YYYY-MM-DD HH:MM:SS` |
| `report_count` / `data_length` / `application_error` | 上报次数 / 数据长度 / 应用层错误 |

### 典型查询

```bash
# 某冻结周期实际采集（权威）：该周期应到多少 STA、缺谁
# freeze_time 格式 YYYY-MM-DD HH:MM:SS；用 LIKE 前缀避免秒级精度差异
sqlite3 idx-*.sqlite3 \
  "SELECT station_key, freeze_time FROM minute_reports WHERE freeze_time LIKE '2026-08-31 14:22%';"

# 页面口径核对：按上报时刻分桶（与页面一致，会含迟报）
# ⚠ time_seconds 实际是毫秒（列名误导）；period_ms = 分钟数×60000，2 分钟周期 = 120000
sqlite3 idx-*.sqlite3 \
  "SELECT time_seconds/120000 AS bucket_2min, COUNT(DISTINCT station_key) AS sta_cnt
   FROM minute_reports GROUP BY bucket_2min;"
```

## 3. 模拟集中器库（主动上报 / 下发查询）

```bash
ls -la .build_plain/data/listener_13762.sqlite*   # WAL 模式：同目录 .wal/.shm，读前先 checkpoint
sqlite3 .build_plain/data/listener_13762.sqlite ".schema frame_log"
```

- `frame_log`：收发双向帧（`dir`=tx/rx，`afn`/`fn`/`updown`=up/down，`frame_hex`，`parsed`，`day` 按天滚动保留 5 天）。
- `report_event`：06H 主动上报事件（`event_type`：F1 从节点信息 / F3 工况变动 / F4 设备类型 / F5 事件）。
- `report_meter_data`：06H F2 抄表数据（`seq_no` / `proto_type` / `uplink_sec` / `payload_hex` / `payload_json`）。
- `query_snapshot` / `query_snapshot_item`：下发查询的临时快照（`mode`=manual/auto，`status`=running/done/partial/error）。

> **记录面不全属正常**：该库只落 06H 主动上报与查询快照；06F230 主动上报帧本身在 `frame_log`
> 完整、但解析明细只在 report_* 表，丢失明细不代表丢帧。

## 4. simcon 会话帧（JSONL）

```bash
ls .build_plain/data/logs/simcon/sc-*.jsonl
jq -r 'select(.dir=="tx") | [.ts,.afn,.fn,.frame_hex] | @tsv' sc-2026*.jsonl   # 只看下发
```

每行 JSON：`seq`、`ts`（ISO 时间）、`dir`(tx/rx)、`kind`、`run_id`、`frame_hex`、`afn`、`fn`、
`updown`(up/down)、`parsed`（1376.2 解析对象）。

## 5. CCO 模块日志（发送侧真相）

```bash
ls .build_plain/data/logs/模块/cco/*.log
grep -aiE "06201c01" *.log   # 06F230 采集上报（详见 cco-log.md）
grep -ai  "11e4"       *.log # 11E4 主动上报通道
grep -ai  "11e3"       *.log # 11E3 补采指令
```

## 6. 组合排查参考链（多端交叉验证）

排查「某周期缺 X」时，允许跨 references 组合（覆盖 listener + simcon + CCO 多端）：

1. **先还原页面口径**：确认页面分桶键（`listener.md` 分桶口径；默认按上报时刻分桶）。
2. **冻结时刻做权威核对**：`minute_reports.freeze_time` 统计该周期实到（查询见上）。
3. **发送侧 ↔ 接收侧交叉**：
   - 目标 STA 在 CCO 日志有 06F230 帧 → CCO 发了；再查侦听台索引有无该帧，无 = 接收侧丢帧；
   - CCO 无 06F230 但有 11e3 补采 → 弱信号节点靠补采才上报（发送侧慢）。
4. **排除链路断线时段**：见第 0 节，先确认链路在线。

> 结论判定速记：**CCO 发了 + 索引没有 = 接收侧丢（真缺）；CCO 没发 = 发送侧问题；链路断 = 非漏**。
