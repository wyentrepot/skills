---
name: wb-listener
description: 什么时候用我：要"看链路上现在正跑什么帧"、"把一份 7E 原始日志/问题归档 ZTTLOG.txt 建索引后查已解析帧"、"判定一轮并发抄表断在哪一跳（S1 发出→S2 ACK/响应→S3 接收）"、"解释某个 STA 为什么入不了网 / 整站离网 / 冲突频发 / 信标消失"，或者"帧查到了却没有协议明细字段"时用我。驱动串口、桥 preflight、烧录、模拟集中器/模拟电表不归我。
argument-hint: "[任务，例如 查这批 0003 帧断在哪一跳 / 解释 rslt=1 入不了网 / 给 ZTTLOG.txt 建索引]"
metadata:
  author: reasonix
  version: "1.0.0"
  applies-to: 任意工作区（<WORKBENCH_ROOT> 路径根解析见 wb-base）
  source: 拆自 ai-control-plane（2026-10-28）
---

# 侦听台 + 网络诊断（wb-listener）

本技能只讲**侦听台**（起停采集、7E 原始日志建索引、已解析帧查询、通信流追踪三段证据链）
与**组网诊断判读**（入网/离网/冲突/信标的症状→查什么→判据）。
归别的子技能的事：帧解析/构帧/离线回验 → `wb-appframe`；
开串口前的桥 preflight、mapping_id 与端口映射、波特率/线参 → `wb-serial`；
v2 任务门面、token/scope、evidence L1/L2/L3 下钻 → `wb-base`；
分钟采集缺报对账（freeze_time 权威口径）→ `mclt-collect-analysis`；
模拟电表 → `wb-simeter`；模拟集中器 → `wb-simcon`。

## 0. 三种取帧来源怎么选（先选来源，再看参数）

| 你要回答的问题 | 取帧来源 | 入口（8790） | 前提 / 代价 |
| --- | --- | --- | --- |
| 链路**此刻**在发生什么（新帧、即时） | 实时观察：起串口采集，帧边收边入库 | `POST /api/ai/v1/listener/ensure`（§1） | 独占 listener 口；结束必须 `stop` 释放 |
| **过去那次**到底发了什么（日志已在盘上） | 已解析帧索引：对任意可读路径建索引 | `POST /api/listener/logs/open`（§2） | 与串口采集**互斥**，采集中建索引 409 |
| 一轮业务**断在哪一跳**（不是二值 pass/fail） | 通信流追踪：回放历史窗 或 live 盯新帧 | `POST /api/ai/v1/listener/traces`（§3） | 特征 `app_id` 必填 + 时间窗或 live |
| 帧查到了但**字段是空的** | 不是取帧问题，是解析后端档位 | `GET /api/version` → `parse_backend`（§5） | `none` 需 Windows 侧起网关，人在 Windows 执行 |

判读顺序恒为「先有来源 → 再取帧 → 再判读」；**不要在没有索引的情况下凭页面印象下结论**。
> 来源：ai-control-plane/references/listener.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

## 1. 实时观察：起停采集（server 侧管串口）

```bash
# 确保侦听台在线（打开串口开始采集）
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/ensure \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"mapping_id":"listener"}'

# 停止侦听台
curl -X POST http://127.0.0.1:8790/api/ai/v1/listener/stop \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"force":false}'
```

- `listener:stop` 校验的 resource：在线时为当前 `mapping_id`（`listener`），离线回退
  `listener-main`；窄授权（`resources` 非 `*`）需**两者都包含**。
- 串口独占：采集中禁止开日志索引（409），索引中禁止启动采集（409）；409 是资源冲突不是故障。起采集前先跑 `/api/serial-bridge/status` + `/verify`，`workbench_ready=false` 不要 ensure
  （字段判读见 `wb-serial`）。
- 串口级参数（`port`/`baudrate 300-921600`/`bytesize 5-8`/`parity N/E/O`/`stopbits 1-2`）属 `/api/serial/start|stop`，同样走侦听台子应用；本技能按 `mapping_id` 走。

> 来源：ai-control-plane/references/listener.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

## 2. 7E 原始日志 → 索引（离线排查标准入口）

> 问题归档里的原始 7E 日志（如 `/01-issuse/.../ZTTLOG.txt`）**无需拷贝**进
> `data/logs/侦听台/`——直接用网关入口对**任意可读路径**建索引，随后走统一帧查询。
> 这是离线数据排查的标准入口（使用经验 #5 固化）。

```bash
# 1) 建索引（202 异步受理；body.path 为绝对路径，≤1024）
curl -X POST http://127.0.0.1:8790/api/listener/logs/open \
  -H "Content-Type: application/json" -d '{"path":"/01-issuse/安徽营销双模/ZTTLOG.txt"}'

# 2) 轮询状态直到完成
curl http://127.0.0.1:8790/api/listener/logs/status

# 3) 查帧（统一帧查询，见 §3.1；index_id 从 status / 索引列表取）
curl "http://127.0.0.1:8790/api/ai/v1/listener/indexes/<index_id>/frames?offset=0&limit=100" \
  -H "Authorization: Bearer <token>"
```

- **入口陷阱**：`POST /api/listener/logs/open`（8790 网关路径）有效；`/api/logs/open` 是
  listener 子应用内部裸路径，**仅直连 8765 独立版可用，经 8790 网关会 404**。
  状态码：202 受理 / 404 路径不存在 / 409 串口采集中 / 503 后端不可用。**互斥**：串口采集中返回 409 —— 先 `listener/stop` 再建索引。
- 建索引后 `GET /api/listener/indexes`、`indexes/{id}/frames` 即可用；索引库
  `apps/listener/runtime/indexes/idx-*.sqlite3` 同时生成，可只读 SQL 直查（数据源表口径见
  `ai-control-plane/references/offline-analysis.md`，入口见 `wb-appframe`）。
- 文件系统辅助：`GET /api/fs/roots`、`/api/fs/list?path=`、`/api/fs/last`；`/api/fs/pick` 弹原生框，非 Windows 返回 501。

> 来源：ai-control-plane/references/listener.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

## 3. 已解析帧查询与通信流追踪

### 3.1 索引清单与帧分页

```bash
curl http://127.0.0.1:8790/api/ai/v1/listener/schema -H "Authorization: Bearer <token>"
curl http://127.0.0.1:8790/api/ai/v1/listener/indexes -H "Authorization: Bearer <token>"
curl "http://127.0.0.1:8790/api/ai/v1/listener/indexes/<index_id>/frames?offset=0&limit=100" \
  -H "Authorization: Bearer <token>"
curl "http://127.0.0.1:8790/api/ai/v1/listener/indexes/<index_id>/frames/<frame_id>" \
  -H "Authorization: Bearer <token>"
```

- 分页参数：`offset`、`limit`（**1–500**）、`query`（关键字）、`nid`、
  `start_time`/`end_time`（`HH:MM:SS` 或 `HH:MM:SS.mmm`）、`after_id`（游标翻页，
  取上一页最后一条 `frame_id`）。
- 单帧详情响应的 `feature_hint` 就是**可反推的特征草稿**，改一改即可 `POST /traces`。
- 双前缀特例（别"修正"它）：子应用自身有 `/api/listener/*` 路由（traces、indexes），经挂载前缀叠加后外部路径是 **`/api/listener/listener/traces`**；indexes 同时暴露两条，故 `/api/listener/indexes/...` 与 `/api/listener/listener/indexes/...` **都有效**。
- 附带只读统计：`GET /api/concurrent/stats?period=15m|30s|1h|900`（最大并发/成功率/平均耗时/重复下发，来源=收发库 frame_log 的 AFN=F1/FN=F1，**不发帧**）。

> 来源：ai-control-plane/references/listener.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

### 3.2 通信流追踪（三段证据链：S1 发出 → S2 ACK/响应 → S3 接收）

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

- `feature`：`app_id` **必填**（0003 并发抄表 / 0001 单表 / 00A1 / 0020 / 0008）；`msg_seq` 留空=聚合；`frm_type`/`dst_tei`/`nid`/`channel`/`app_raw_contains` 可选。scope 粒度：`flow`（须给 `msg_seq`）/ `round` / `campaign`。
- `response_policy` 可选：`cluster_gap_seconds`（空闲切簇阈值，缺省 60s）、`expect_meters`（显式目标名单）、`use_ack_evidence`/`confirm_via_0x0020`（缺省 true）、`timeout_ms`。
- **msg_seq 取值来源（易踩坑）**：`feature.msg_seq` 匹配的是 `trace_extract` 从 APP_RAW 业务头（`[4:6]` LE16）**物化**进 `frames.msg_seq` 列的报文序号（如 `1EC2`）；它与帧列表/详情里展示的 MAC 层 `Msdu_seq`（如 `AFBC`）**不同源、数值无关**——照页面展示值查询会 0 命中。取值前先用单帧详情的 `feature_hint` 反推，或直接留空聚合。
- 报告结构：`summary`（rounds/meters/full_chain/no_ack/no_response/denied/no_confirm）+ `rounds[]`（时间簇 → `flows[]` 状态机链 `sent→acked→responded→confirmed/denied/timeout`，每阶段挂 `frame_id` 可回帧详情钻取；`meter_table` 表地址 ok/denied/missing 三分类）+ `proxy_graph`（表地址→应答 STA 代理观测）+ `bad_frames`（坏帧只计数，不参与判定）。
- 状态码 422 参数非法 / 503 后端不可用；`DELETE /traces/{trace_id}` 停止并移除 live 句柄（坏帧只计数）。

> 来源：ai-control-plane/references/listener.md；ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md

### 3.3 分钟采集口径（只给指针，细讲不在这里）

「分钟采集分析」页面的分桶键是 `time_seconds % period_ms`（**上报时刻**），权威归属是 `freeze_time`
（冻结时刻）；迟报/补采时两者不一致会造出**假缺报**。完整口径（分桶 SQL、`/listener/minute-periods`
参数 `task_no`/`cco_tei`/`period_minutes 1–1440`/`nid`/`start_time`/`end_time`、REQS-0018）见
`mclt-collect-analysis` 与 `ai-control-plane/references/listener.md`；v2 语义查询
（`investigations` 的 `trace_query`/`minute_periods`、L1/L2/L3 下钻）见 `wb-base`。

## 4. 网络诊断：症状 → 查什么 → 判据

> 本篇是**判读知识**；取证动作按 §4.1 的 L1→L4 走 API，门限/规则 id 见 §4.3，
> 口径与 `libs/network_assert` 断言规则库、侦听台评估 B 类规则一致；
> 事实来源：蒸馏库 `CCO实现逻辑/07-NWK`、`08-MAC`、`13-文档与代码差异记录`、`06_测试用例`（国网口径）。先证据后判定：**没有 L1/L2 证据不要给根因**。

### 4.1 取证路径（低 token 优先）

1. **L1 结论**：`GET /api/listener/network/digest`（8790；独立版 8765 用 `/api/network/digest`）
   ≤4KB——`verdict` 一句话判定 + `level`(alarm/watch/normal) + 异常清单（类型/计数/首末时间/
   人话示例）+ 网络概要 + 自适应时间桶计数（桶内含异常数，用于定点定位时段；跨度 ≤30min 用 1 分钟、更大取 ≤60 桶）。
2. **L2 事件流**：`GET /api/listener/network/events?level=alarm,watch&start_time=&end_time=&limit=`
   ——`level` 过滤降噪（alarm 异常 / watch 关注 / normal 常规，缺省全量）；事件带 `human`
   （TEI→表号人话摘要）、`src_label`/`dst_label` 翻译列，`fields` 仍带全量解析字段（如 assoc_cnf
   的 `rslt`/`retry_time_ms`/`proxy_tei`）；`group` 枚举 组网/维护/冲突/路由/信标/业务，
   `direction` 枚举 down/up/mesh，`limit≤1000`；锁定时段用 digest 返回的桶窗（12 字符毫秒精度）。
3. **L3 单帧粗略解析**：`GET /api/listener/network/events/{frame_id}/brief` ≤2KB——分层中文摘要
   （GW 封装/MAC 头/管理表字段）+ 事件人话 + warnings；点击排查时按需调用，不必整页预载。
4. **L4 信标/评估**：`/api/listener/network/beacons`（`bcn_type=beacon_central`，`fields.periods_ms{beacon,tdma,csma,bind_csma}` 四时段重建）、`/network/assessment`（三级判级）、`/network/status`（≤1KB 快照，仅要评级时用）、`/network/overview`（链路计数器 `sack_fail_rate`/`icv_fail`/`decode_fail`）。
5. 判级口径：`libs/network_assert/rules/*.json`（8 条断言声明，含出处）；digest 的异常分级是服务层轻量内联版（rslt∉{0,0xA} / 离网 / NID·信道冲突 / 路由错误 / BPCS 失败=alarm；代理变更 / 网间协调 / 成功率<90%=watch），**门限出处与 §4.3 同源**；用例背景查 `/api/dict/cases`（269 项）。

### 4.2 组网状态机与关联结果码

```
UNASSOC ──关联确认成功──► ONNET ──第1个心跳周期无心跳──► OFFLINE
   ▲                                                      │连续4个心跳周期无心跳
   └──────────重新关联成功────────────────────────────── WAITON ◄─┘（发离网指示，10s 后删除）
```

| 码 | 枚举 | 含义 | 诊断指向 |
| --- | --- | --- | --- |
| 0 | SUCCESS | 关联成功 | — |
| 1 | OUTOFLIST | 不在白名单 | 档案 MAC 与 STA 实际不符 / 白名单池未装载完（上电分批 `laddPollInit`）；退避 40/60/600s 分档 |
| 2 | INBLACKLIST | 在黑名单 | 黑名单按分钟刷新（`BlackListTimeFlush`） |
| 3 | STANUM_LIMIT | 站点超上限 | `STA_NUM_MAX=1023` / TEI 空闲池耗尽 |
| 4 | WLIST_NOSET | 未设白名单 | 自上而下（有档案）模式必须先设白名单 |
| A | DUP_SUCCESS | 再次关联成功 | 重入网保号（`readd`），**非故障** |
| B | TRY_SUB_SITE | 试图以自己的子站点为代理 | 拓扑异常 |
| C | LOOP_EXIST | 存在环路 | 拓扑/中继异常 |
| E | RFPCO_LIMIT | RF 代理超限 | `rfProxyLimitEn` 代理总数 / RF 跳数超限 |
| F | UNKNOWN | 其他（含全 00/99/FF 特殊地址禁入网） | 地址非法或未分类原因 |

拒绝退避档位（`nwk_reject_list.c:115-119` + `cac.h:173-178`）：上电 <121s 防洪泛档（40s）→ 121~1800s（60s）→ >1800s（600s）；开关关闭时按 MAC 指数退避 `16×2^cnt` 秒，上限 6 次。

### 4.3 门限速查表（判据；与 `libs/network_assert` 同口径）

| 门限 | 值 | 规则 id | 出处 |
| --- | --- | --- | --- |
| 关联拒绝退避分档 | 40/60/600s，边界 121s/1800s | `nwk.assoc_reject.backoff_tiers` | 07 §1.4 |
| 心跳缺失离网 | 第 1 周期 OFFLINE；连续 4 周期 WAITON+离网指示；10s 后删除 | `nwk.heartbeat.offline_4cycles` | 07 §5.4 |
| 心跳周期 | 路由周期×2（≤20 站）/×4（>20 站） | `nwk.heartbeat.period_ratio` | 07 §5.4 link.c:390 |
| 信标周期合法域 | 协议 1~10s；评估参数口径 500ms~120s（实测 14878ms） | `nwk.beacon.period_domain` | 06 §7.3 + 评估 |
| 路由周期 | <20 站 60s；否则 ceil(n/20)×50s，钳位 [50,720]s | `nwk.route.period_adaptive` | 07 §6.4 |
| CSMA 时隙占用 | >60% 降级、>80% 故障（占比=CSMA 时隙/信标周期） | `nwk.csma.occupancy_two_tier` | 评估 B 档 |
| 通信成功率三级 | ≥98% 健康 / 90~98 亚健康 / <90 故障；离线率 ≤2 / 2~10 / >10% | `nwk.comm_success_rate.three_tier` | 评估 A 档 |
| 冲突仲裁时序 | NID：307ms/30min；RF：20.7s/30min（协调帧触发一律 307ms/20.7s）；t2=5min 解除；切换 100s+确认 102s | `nwk.conflict.arbitration_timing` | 07 §7 |
| STA 主动离网口径 | 两路由周期无信标 / 连续 4 路由周期成功率 0 / 层级>15 / 组网序列号变化 / 收到离线指示 | — | 06 §2.5.2.11 |

### 4.4 故障特征 → 根因映射（症状→先查→根因方向；括号内为可复核的规则 id）

| # | 症状 | 先查（证据） | 根因方向 | 依据 |
| --- | --- | --- | --- | --- |
| 1 | 无法入网·被拒 rslt=1 | assoc_cnf.rslt、retry_time_ms | 档案地址与 STA 实际 MAC 不符；白名单池上电分批装载未完成 | 07 §1；`nwk.assoc_reject.backoff_tiers` |
| 2 | 无法入网·rslt=4 | CCO 白名单标志/档案下发 | 自上而下模式未设白名单即开放入网 | 07 §1.4 cac.c:87 |
| 3 | 无法入网·rslt=3 | 在网站点计数、TEI 池 | 1023 上限或空闲池耗尽（TEI 未回收） | 07 §2 |
| 4 | 无法入网·rslt=2 | 黑名单事件 | STA 曾被拉黑，按分钟刷新等待/移除 | 07 §2.4 |
| 5 | 无法入网·rslt=E | RF 代理计数/跳数 | rfProxyLimitEn 代理总数或 RF 级联超限 | 07 §1.4 |
| 6 | 无法入网·rslt=B/C | 拓扑/中继事件 | 以子站点为代理或环路，选代理被拒 | 07 §3.4 |
| 7 | 反复重关联（入网后周期性掉） | leave_ind 事件、心跳计数 | 心跳 4 周期判离网；台区心跳转发缺失（代理变更请求视作心跳补救） | 07 §5；`nwk.heartbeat.offline_4cycles` |
| 8 | 反复重关联·成批发生 | 信标 NWKFormNo | 组网序列号变化（CCO 重组网）→STA 集体主动离网重入 | 06 §2.5.2.11 |
| 9 | 整站离网·伴随 NID/信道事件 | conflict 组事件 | NID 冲突改 NID（307ms/30min 仲裁）或 RF 信道切换（100s 切换）期间全网迁移 | 07 §7；`nwk.conflict.arbitration_timing` |
| 10 | 整站离网·信标消失 | beacons 到达间隔 | CCO 停发信标（掉电/守护重启），按信标周期计数断档定位 | 07 §6 |
| 11 | 部分离网·链路劣化 | 通信成功率上报 | STA 连续 4 路由周期成功率 0 主动离线 | 06 §2.5.2.11；`nwk.comm_success_rate.three_tier` |
| 12 | 部分离网·信标收不到 | 信标/发现列表老化 | STA 两路由周期无信标主动离线；RF 接收率老化 5 周期 | 06 §2.5.2.11；07 §8 |
| 13 | 代理震荡 | 代理变更请求帧占比（>8% 判降级） | 信道劣化触发 table79 重选；确认在位图式/TEI 式间交替保证可靠切换 | 评估稳定性 + 07 §3 |
| 14 | 冲突频发 | rf_conflict/nid_conflict 事件、SACK 失败率 | 邻网 CCO MAC 仲裁避让反复；VCS 前导误检（工程 EIFS/12、/8） | 07 §7 + 08 §6 |
| 15 | 心跳丢失但表计在位 | 心跳位图、路由周期 | 心跳档位误判（>20 站 ×4）；PCO 子站位图 OR 汇聚缺失 | 07 §5；`nwk.heartbeat.period_ratio` |
| 16 | CSMA 拥塞 | table50 四时段占比 | 占比 >60%/80% 两级判级；业务洪峰或时隙规划失衡；minBE=4 退避重传加剧 | 08 §1-2；`nwk.csma.occupancy_two_tier` |
| 17 | 通信成功率低 | 评估成功率三级 | 链路质量（SNR/RSSI 一阶滤波）、重传 NB/BE 封顶（maxBE=8）仍失败 | 评估 A 档 + 08 §2 |
| 18 | 疑似广播风暴 | 重传帧计数 | 代理广播判重四要素未命中的重复帧（缓存 128 项，重启次数不同视为新帧） | 08 §8 |
| 19 | 升级/并发互扰 | 升级窗口、并发队列 | 升级期间并发上限临时压到 5；AFN=F1H 并发队列条目 5 分钟生命周期自消亡 | 13 号 #41 |
| 20 | 层级超限离网 | 代理信标条目 47 层级 | STA 层级>15 主动离线；多级代理规划失衡 | 06 §2.5.2.11 |

### 4.5 信标/时隙速查

- **中央信标**：table38 头（type=2、允许关联、组网序列号 NWKFormNo、CCO MAC）→ 条目顺序 47 站点能力 → 48 路由参数 → 54 无线路由 → 万年历 → 50 时隙分配 → 49 频段变更 → 55 无线频道变更；载荷尾 BPCS 32bit CRC。
- **四时段**（table50）：信标 / TDMA / CSMA / 绑定CSMA；CSMA 时段提前 2ms 结束，TDMA 时隙提前 400us，信标发送延迟 1200us；`CSMAStartNTB=(信标+TDMA 时长)×25000`。
- **NTB** 单位 0.04us（25MHz）；CIFS 载波 400us / 无线 800us；RIFS 2300us；EIFS 协议 20/70ms（工程 /12、/8 抗前导误检）；网间协调帧 1900ms 一个序号，带宽退避 = 重叠量+对方时长+20ms；频段/频道变更剩余时间 >100ms 才在信标宣告（table49/55），全网同步切换。**编址/路由**：TEI 12bit（0 非法、1=CCO、2..1023 站点、4095 广播）；层级上限 15；每站路由表 4 个下一跳（`rte[0]` 最新）；RouteError ≤15 个不可达 TEI，仅解析不联动删路由。

### 4.6 判读时容易踩的文档-代码差异

1. **超时/缓存**：并发抄表业务文档 60s、实现 99s（`CONC_METER_TRANS_MAX_SEC`）；报文过滤缓存文档 8 帧、实现 128 项哈希环形表。
2. **时隙参数**：VCS 前导忙协议 EIFS 20/70ms、实现 `HPLC_EIFS/12`≈1.67ms 与 `RF_EIFS/8`；CSMA 最小退避指数 minBE=4（注释"由 2 改为 4"）、maxBE=8。
3. **时间/类型/路由**：掉电第一阶段文案 80s、实现 70000ms，上电波特率探测只轮换 9600E/115200N/115200E 三档；定界符类型 0=信标帧（MAC 帧控制）而 `table38_stuff_type` 填 2 表示"中央信标"，两个"类型"不是一回事；RouteError 仅解析不联动删路由、LinkConfirmRequest 构帧未发送。

> 来源：ai-control-plane/references/network-diagnostics.md；ai-control-plane/references/api-contract.md

## 5. 解析后端：本地 / Windows 网关 / 无（REQS-0019）

侦听台深度解析按三档降级：`local`（WSL 本机 net8.0 DLL）/ `remote`（委托 **Windows 解析网关**
`172.25.0.1:8700`，net48 DLL）/ `none`（无解析后端——帧照常采集入库、可查，但**深度解析字段不可用**）。

- **查档位**：`GET http://127.0.0.1:8765/api/version` → `parse_backend`（及 `dll_available`）。
- `none` 时 `/api/parse`（8765）返回 503，**不影响**串口采集与日志索引。
- **起网关（Windows 侧，需人在 Windows 执行）**：桌面 `wsl环境部署.bat` → [4] 启动 / [5] 停止；或 `powershell -File <WORKBENCH_ROOT>/tools/scripts/uart-map.ps1 -Action start-gateway`（详见 `<WORKBENCH_ROOT>/tools/scripts/README.md`）。WSL/Linux 侧无此步骤。
- **排查提示**：帧缺协议明细时先看 `parse_backend`；`none` → 先起网关再继续，别怀疑数据/链路；窄带（双模 HPLC/RF）报文的深度字段同样依赖该档位，Linux 侧无法自足。

> 来源：ai-control-plane/references/listener.md；ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md

## 6. 红线

1. **用完即停**：采集完 `listener/stop`，索引任务结束不留常驻；不开任务外的会话。
2. **409 不硬抢**：串口归一主，409（采集中/被占用）时等待或换口，不并发重试、不换口偷跑。
3. **不开任务外的源、索引库只读**：只对本次排查需要的路径建索引；`data/logs/` 之外的原始 7E 日志不拷贝、不改名、不清理；`idx-*.sqlite3` 只允许 SELECT，不写/不改/不删。
4. **少拉数据**：`limit` 默认 100 量级（上限 500），先 L1/L2 再 L3，避免整库拉成上下文。
6. **token 不外泄**：不要把 `Authorization` 值写进输出、日志或提交内容。

## 7. 参考

- 源文件与已读小节见文末附录；判级规则库：`libs/network_assert/rules/*.json`（相对 `<WORKBENCH_ROOT>`）；用例库 `/api/dict/cases`。
- 解析依据：`libs/parser_lib/adapters/adapter_dualmac/`（GW 封装剥离 + 4-2 表 13/4/17/19/23/26/30/34/38/47/48/49/50/54/55/57 + NWK 管理帧 table60/70/76/79/84/88/91/94/100/102/111/114/117/118/121）；NID 展示为 24bit 小端十六进制（如 947F69），查询同时匹配字节序反转写法（697F94）。

> 来源：ai-control-plane/references/network-diagnostics.md；ai-control-plane/references/api-contract.md

---

## 附录 · 深水事实库（事实来源，按节读，不复制）

本技能只讲**怎么做**。精确字段、全部端点、全流程手册在入口技能的事实库里，**只有本文答不清或要核对字段时才翻对应小节**，不要整份读：

| 文件 | 该读哪一节 | 行数 |
|---|---|---|
| ai-control-plane/references/listener.md | 侦听台全部端点与索引/帧查询细节 | 184 |
| ai-control-plane/references/network-diagnostics.md | 入网/离网/冲突/信标的判据全表 | 112 |
| ai-control-plane/references/api-contract.md | §3 侦听台契约 | 491 |

- 旧门面归档（v2.9 路由表、实测校准段、REQS 编号索引）：ai-control-plane/references/_归档-门面v2.9.md（257 行，**仅当新文档查不到时**参考）

> 铁律：事实库里改动只改一处；子技能里**不复制**事实库内容，避免两份说法打架。
