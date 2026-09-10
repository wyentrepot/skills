# API 契约文档（事实来源：后端代码）

> 基线：workbench OpenAPI（运行 `python tools/scripts/verify_api_inventory.py` 校验）。本文档从后端路由代码逐条核对生成，
> **改接口必须先改代码、再同步本文件**；开发新功能或排查联调问题按本文件对账。
>
> 事实来源文件（改动接口时同步核对）：
> - 侦听台：`apps/listener/app.py`
> - 模块日志：`apps/module_log/app.py`（loghooks 路由也在其中）
> - 模拟集中器：`libs/sim_concentrator/api.py`
> - AI 控制面：v2 任务门面 `apps/workbench/ai_v2_api.py`；v1 专家兼容层 `apps/workbench/ai_api.py`（用法手册：`.agents/skills/ai-control-plane/SKILL.md`、`docs/16-AI操作指南.md`）
> - 编排：`apps/workbench/api.py`；字典：`apps/workbench/dict_api.py`；串口 Profile：`apps/workbench/serial_profile_api.py`
> - 挂载/代理：`apps/workbench/app.py`（`_PrefixProxy` / `_mount_proxied`）

---

## 1. 部署形态与 API 前缀映射（最重要）

### 1.1 入口

| 入口 | 启动 | 端口 | 静态目录 | 说明 |
| --- | --- | --- | --- | --- |
| 统一工作台 | `apps/workbench/run.py` | **8790** | `apps/workbench/static/`（挂 `/static`） | 页面在 `/static/pages/<页名>/`，外壳 `/` |
| 侦听台独立版 | `apps/listener/run.py` | 8765 | `apps/listener/static/` | API 无业务前缀 `/api/*` |
| 模块日志独立版 | `apps/module_log/run.py` | 8766 | `apps/module_log/static/`（`/module-serial` 页面） | API 自带 `/api/module-serial/*` |
| simcon 独立版 | `python -m sim_concentrator.api` | 8781 | 无 | 路由 `/api/simcon/*` |

### 1.2 workbench（8790）挂载表 —— 外部路径 → 子应用内部路径

代理语义（`_PrefixProxy`）：**外部路径 = `{api_prefix}{rest}` → 子应用收到 `{sub_root}{rest}`**。

| 外部前缀 | 子应用 | sub_root | 语义 |
| --- | --- | --- | --- |
| `/api/listener/*` | listener | `/api` | **剥业务段**：`/api/listener/logs/status` → 子应用 `/api/logs/status` |
| `/api/module-serial/*` | module_log | `/api/module-serial` | 透传 |
| `/api/fs/*` | module_log | `/api/fs` | 透传 |
| `/api/loghooks/*` | module_log | `/api/loghooks` | 透传 |
| `/api/simcon/*` | module_log（内部又挂 simcon 子应用） | `/api/simcon` | 透传 |
| `/api/ai/v1/*` | workbench 自身（ai_api router） | — | AI 控制面 |
| `/api/*`（其余） | workbench 自身（编排/字典/串口 Profile router） | — | 见 §4/§7/§8 |
| `/static/*`、`/` | workbench 静态外壳 | — | NoCacheHTMLStaticFiles |

**双前缀特例（易踩坑）**：listener 子应用自身有一组 `/api/listener/*` 路由
（traces、indexes，见 §3.2）。经挂载前缀叠加后，workbench 外部路径是
**`/api/listener/listener/traces`**（双 `listener`）。页面前端（trace.js）就是这么调的，勿"修正"。
子应用同时把 indexes 暴露为 `/api/indexes` 与 `/api/listener/indexes` 两条，
故外部 `/api/listener/indexes/...` 与 `/api/listener/listener/indexes/...` **都有效**。

**挂载降级**：listener 依赖 C# DLL/pythonnet，挂载失败自动降级
（`/api/platform-version` 里 `listener_mounted=false`，页签显示"不可用"，不拖垮整体）。

### 1.3 通用约定

- **统一错误响应（D-04）**：`{code, message, details, request_id}`，兼容旧 `detail` 字段（`apps/workbench/errors.py` 注册）。
- **状态码语义**：`202` 异步受理（开日志索引/启动采集/烧录/观察/AI 长任务）、`201` 创建成功（会话/授权）、
  `409` 资源冲突（串口占用/互斥运行）、`422` 参数校验失败、`404` 资源不存在、`503` 服务未启用/降级、
  `501` 非 Windows 原生文件选择。
- 互斥关系：串口采集运行中禁止开日志索引（409）；日志索引中禁止启动串口（409）。
- 分页约定（帧列表）：`offset/limit(≤500)/query/nid/start_time/end_time/after_id`，增量拉取用 `after_id`。
- HTML/静态资源全部禁缓存（`NoCacheHTMLStaticFiles` + 工具页 meta）。

---

## 2. 平台端点（workbench 自身）

| 方法 | 路径 | 响应要点 |
| --- | --- | --- |
| GET | `/` | 外壳 `index.html` |
| GET | `/api/platform-version` | `{app, version, module_log_mounted, listener_mounted}`（外壳页脚探测用） |
| GET | `/api/health` | `{status:"ok", app:"workbench"}`（AI/脚本探活入口） |

## 3. 侦听台 listener

"内部路径"= 独立版 8765 直接可用；workbench 外部路径按 §1.2 推导（`/api/X → /api/listener/X`）。

### 3.1 版本/解析/文件系统

| 方法 | 内部路径 | 参数/请求体 | 响应要点 | 状态码 |
| --- | --- | --- | --- | --- |
| GET | `/api/version` | — | `{picker_api_revision:2, minute_analysis_api_revision:3, frame_filter_api_revision:2, serial_api_revision:1, dll_available, name, version, date}`（DLL 缺失时无 name/version/date） | 200 |
| POST | `/api/parse` | `{hex}` | 解析结果 JSON（ParserService） | 503 DLL 不可用 / 422 帧校验 / 500 |
| GET | `/api/fs/roots` | — | `{roots:[{name,path}]}` | 200 |
| GET | `/api/fs/list` | `?path=` | 目录清单（shared.infra） | 400 缺 path |
| GET | `/api/fs/last` | — | `{path}`（上次所选目录） | 200 |
| GET | `/api/fs/pick` | — | `{path}`（弹原生文件框） | 501 非 Windows |

### 3.2 日志索引与帧

| 方法 | 内部路径 | 参数/请求体 | 响应要点 | 状态码 |
| --- | --- | --- | --- | --- |
| POST | `/api/logs/open` | `{path≤1024}` | 索引任务受理（异步，轮询 status） | **202** / 404 / 409 串口运行中 / 503 |
| GET | `/api/logs/status` | — | LogFileService.status() 结构 | 503 |
| GET | `/api/logs/frames` | `offset,limit≤500,query,nid, start_time,end_time,after_id` | LogFileService.list_frames()（增量用 after_id） | 422 / 503 |
| GET | `/api/logs/frames/{frame_id}` | — | 单帧详情（含解析字段） | 404 / 500 / 503 |
| GET | `/api/logs/minute-analysis` | `period_minutes≤1440, cco_tei(3位hex), nid` | `{periods, summary{total_periods,report_count}, delete_config_stats, filters}` | 422 / 503 |
| GET | `/api/logs/delete-config-details` | `cco_tei, nid` | `{down_count, up_count, down[], up[], filters}` | 422 / 503 |
| GET | `/api/indexes` ＋ 别名 `/api/listener/indexes` | — | 索引清单（LogFileService.list_indexes()） | 503 |
| GET | `/api/indexes/{index_id}/frames` ＋ 别名（同参数同 §3.1 帧参数） | 同上 | LogFileService.list_index_frames() | 404 / 422 / 503 |
| GET | `/api/indexes/{index_id}/frames/{frame_id}` ＋ 别名 | — | 单帧详情 | 404 / 500 / 503 |

workbench 外部：`/api/indexes/... → /api/listener/indexes/...`；别名路由对应外部
`/api/listener/indexes/... → /api/listener/listener/indexes/...`（两者均可用）。

### 3.3 任务报文分析（task-config 系列）

| 方法 | 内部路径 | 参数 | 响应要点 |
| --- | --- | --- | --- |
| GET | `/api/logs/task-minute-analysis` | `task_no(1-3位数字,必填), period_minutes?, cco_tei, nid, start_time?, end_time?` | ListTaskMinutePeriods 结构 |
| GET | `/api/logs/task-derived-period` | 同上（无 period_minutes） | task_derived_period() |
| GET | `/api/logs/task-config-tasks` | `cco_tei, nid, start_time?, end_time?` | `{tasks:[...]}` |
| GET | `/api/logs/task-config-summary` | `task_no(必填), cco_tei, nid, start_time?, end_time?` | 汇总 + `filters` |
| GET | `/api/logs/task-config-lifecycle` | `task_no(必填), cycle_index?, cco_tei, nid` | 生命周期汇总 |

### 3.4 网络承载评估

| 方法 | 内部路径 | 参数 | 响应要点 |
| --- | --- | --- | --- |
| GET | `/api/network/assessment` | `index_id?, start_time?, end_time?, nid?` | 完整评估；无信标时 `{networks:[], beacon_period_ms:null, fallback:"beacon_undetected", message}` |
| GET | `/api/network/status` | 同上 | **AI 用轻量快照 ≤1KB**：`{networks[{nid,cco_mac,beacon_period_ms,overall_health,latest_success_rate}], beacon_period_ms, overall_health, latest_cycle{start_time,end_time,success_rate,rating}, fallback}`；rating 枚举 healthy/degraded/fault |

### 3.4a 组网观测（REQS-0024/0026）

| 方法 | 内部路径 | 参数 | 响应要点 |
| --- | --- | --- | --- |
| GET | `/api/network/events` | `index_id?, start_time?, end_time?, nid?, event?, group?, direction?, query?, level?, limit≤1000, offset?` | 组网事件流（首次调用触发增量扫描，`refresh.pending` 表示存量未扫完再点刷新）；`group` 枚举 组网/维护/冲突/路由/信标/业务；`direction` 枚举 down(CCO→)/up(→CCO)/mesh；`level` 逗号分隔 `alarm,watch,normal`（0026 降噪过滤，缺省全量）；事件 `fields` 含该类报文全量解析字段（如 assoc_cnf 的 rslt/retry_time_ms/proxy_tei），并附 `level`（三级分级）+ `human`（TEI→表号人话摘要）+ `src_label`/`dst_label` 翻译列 |
| GET | `/api/network/digest` | `index_id?, start_time?, end_time?, nid?` | **印象结论包 ≤4KB（0026，人 + AI 同源 L1）**：`{verdict 一句话判定, level(alarm/watch/normal), alarm_count, watch_count, event_total, alarms[{type,name,count,first_time,last_time,sample_human}]≤6, watch[]≤3, network{nid,cco_mac,station_count}, quality{frames_total,sack_*,icv_fail,truncated,decode_fail}, scan_pending, buckets[{start,end,total,alarms}]≤60 非空桶, bucket_seconds}`；时间桶自适应粒度（跨度 ≤30min 用 1 分钟，更大取 ≤60 桶取整）；异常分级门限出处：蒸馏库 07-NWK/08-MAC（rslt∉{0,0xA} 被拒、离网、NID/信道冲突、路由错误、BPCS 失败=alarm；代理变更、网间协调、成功率<90%=watch） |
| GET | `/api/network/events/{frame_id}/brief` | `index_id?` | **单帧粗略解析 ≤2KB（0026 按需 L3）**：`{frame_id, log_time, nid, layers[{title,fields{中文键:值}}]（GW封装/MAC头/管理表·信标/选择确认/业务载荷）, events[{level,name,human}], warnings[]}`；帧不存在 404，解析失败 422 |
| GET | `/api/network/overview` | `index_id?, start_time?, end_time?, nid?` | `{networks[{nid,cco_mac,beacon_period_ms,stations,station_count,event_count}], event_type_counts, link_counters{frames_total,mgmt_total,app_total,beacon_total,sack_total,sack_fail,sack_fail_rate,icv_fail,truncated,decode_fail}, groups, event_names}` |
| GET | `/api/network/beacons` | `index_id?, start_time?, end_time?, nid?, bcn_type=beacon_central, limit≤200` | 信标明细；`fields.periods_ms{beacon,tdma,csma,bind_csma}` 为四时段重建（ms，相对信标周期起始），`fields.csma_slots` 为各相分片 |

> 0026 前端分工：组网观测卡片区只保留事件侧统计（事件数/异常数/SACK 失败率/ICV 失败），信标周期/CSMA 占用等信道质量指标归网络承载评估页；评估页异常周期有「下钻排查」按钮，带周期时间窗跳转组网观测。

> 解析依据：`libs/parser_lib/adapters/adapter_dualmac/`（GW 封装剥离 + 4-2 表13/4/17/19/23/26/30/34/38/47/48/49/50/54/55/57 + NWK 管理帧 table60/70/76/79/84/88/91/94/100/102/111/114/117/118/121）；位域经 reqs/0009 真机样本 2276 帧实证，BPCS/ICV 校验通过口径见模块 docstring。NID 展示为 24bit 小端十六进制（如 947F69），查询同时匹配字节序反转写法（697F94）。

### 3.5 通信流追踪（需求 0009，注意双前缀）

| 方法 | 内部路径 | workbench 外部路径 | 请求体 | 响应要点 | 状态码 |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/listener/traces` | **`/api/listener/listener/traces`** | `{window:{mode:"live"\|...}, ...}`（TraceService） | live → 注册句柄；否则同步回放结果 | 422 / 503 |
| GET | `/api/listener/traces` | `/api/listener/listener/traces` | — | `{traces:[live清单]}` | 503 |
| GET | `/api/listener/traces/{trace_id}` | 同上规则 | — | live 快照 | 404 / 503 |
| DELETE | `/api/listener/traces/{trace_id}` | 同上规则 | — | 停止并移除 | 404 / 503 |

### 3.6 串口实时采集

| 方法 | 内部路径 | 参数/请求体 | 响应要点 | 状态码 |
| --- | --- | --- | --- | --- |
| GET | `/api/serial/ports` | — | `{ports, port_details, mapping_error}` | 503 |
| GET | `/api/serial/status` | — | SerialCaptureService.status() | 503 |
| POST | `/api/serial/start` | `{port, baudrate 300-921600, bytesize 5-8, parity N/E/O, stopbits 1-2}` | 受理 | **202** / 409 索引中或已运行 / 500 / 503 |
| POST | `/api/serial/stop` | — | 停止结果 | 503 |

## 4. 模块日志 module-serial（`/api/module-serial/*`，两形态同路径）

### 4.1 动态会话 API（新前端与 AI 控制面用）

| 方法 | 路径 | 请求体 | 响应要点 | 状态码 |
| --- | --- | --- | --- | --- |
| GET | `/sessions` | — | `{sessions:[...]}` | 503 |
| POST | `/sessions` | `{title≤128, module:cco\|sta}` | 会话对象 | **201** / 503 |
| GET | `/sessions/{id}` | — | 会话对象（含 port_identity/log_file） | 404 |
| PATCH | `/sessions/{id}` | `{title?, module?}` 至少一项 | 更新后对象 | 422 全空 / 404 |
| DELETE | `/sessions/{id}` | — | 删除结果 | 404 |
| POST | `/sessions/{id}/start` | `{port, baudrate, bytesize, parity, stopbits}` | 受理 | **202** / 404 / 409 |
| POST | `/sessions/{id}/stop` | — | 停止结果 | 404 / 409 |
| POST | `/sessions/{id}/write` | `{data 1-4096}` | 写入结果 | 404 / 409 |
| POST | `/sessions/{id}/write-text` | `{text≤4096, append_newline=true}` | 写入结果 | 404 / 409 |
| POST | `/sessions/{id}/baudrate` | `{baudrate}` | 设置结果 | 404 / 409 |
| POST | `/sessions/{id}/flash` | `{bin_path, slot 0-1, baud_plan?, no_reboot_after=false}` | 烧录结果 | 404 / 409 |
| GET | `/sessions/{id}/logs` | `?after=-1` | 增量日志（lines + 游标） | 404 |

### 4.2 旧单/双通道 API（兼容保留）

`/start`（`{port,...,log_type:cco|sta, channel?}`，202）、`/stop`（`{channel}`）、
`/write`（`{data,channel}`）、`/write_text`（`{text,channel,append_newline}`）、
`/baudrate`（`{baudrate,channel}`）、`/flash`（`{bin_path,slot,baud_plan?,no_reboot_after,channel}`）、
`/logs?after&channel`、`/status`、`/ports`（`{ports, port_details, mapping_error}`）。

### 4.3 其他

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/module-serial/version`（内部另有 `/api/version`） | `{app:"module-serial", module_serial_api_revision:2, channels}` |
| POST | `/api/module-serial/upload` | `{name≤255, base64≤10MB}` → `{path}`（422 解码失败/空文件） |
| GET | `/api/fs/roots`、`/api/fs/list?path`、`/api/fs/pick` | 与 `/api/module-serial/fs/*` 双暴露同实现（workbench 经 `/api/fs` 透传） |
| GET | `/api/loghooks/scan?path&module&limit≤20000` | 扫日志文件；`/api/module-serial/loghooks/scan` 双暴露；404 error |
| GET | `/api/loghooks/realtime?session_id&channel&limit` | 实时会话内存日志扫描；带 `source{kind,session_id|channel,...}` |
| GET | `/api/loghooks/sources` | `{root, groups{cco[],sta[]}}` |

## 5. 模拟集中器 simcon（`/api/simcon/*`，三形态同路径）

| 方法 | 路径 | 参数/请求体 | 响应要点 | 状态码 |
| --- | --- | --- | --- | --- |
| GET | `/status` | — | `{open, port, port_identity, mapping_error, pending_frames, session}` | 200 |
| GET | `/ports` | — | `{ports, port_details, mapping_error}`（simcon 用未映射端口） | 200 |
| GET | `/responders` | — | `{rules:[内置+覆盖应答规则]}` | 200 |
| POST | `/open` | `{port?, mapping_id?, baudrate?, bytesize?, parity?, stopbits?}` 全可省（走映射默认） | `{open:true, port, mapping_id, port_identity, session_id, baudrate, bytesize, parity, stopbits}` | 409 打开失败 |
| POST | `/close` | — | `{open:false}` | 200 |
| POST | `/verify` | VerifyTask `{id?, port?/mapping_id?..., enable_responder=true, fail_fast=true, responders?, steps:[{send,expect,expect_timeout,...}]}` | 逐步判定 + `summary{total,pass,fail,verdict}`；空任务不碰串口仍返映射解析 | 409 |
| POST | `/step` | `{send?, profile?, expect?, expect_timeout=null, auto_expect=true, expect_no_reply=false, recv_only=false, enable_responder=true, name?}`；send 只写 afn/fn+params（ADR-5，raw 报错）。REQS-0027：`expect_timeout=null` 时按 expect_rules per-Fn 档位自动取值（默认 5s/单抄 59s/并抄 99s）；`auto_expect=true` 且未显式 expect 时按规则库自动生成，结果附 `step.pairing{rule_id,desc,expect,form,timeout}`、否认帧附 `step.deny{code,code_hex,text}`、插播帧附 `step.bystanders[]` | 单步执行结果（seq 自增） | 422 / 409 |
| POST | `/build` | `{afn, fn, params{}, direction=down, profile?, seq=1}` | **只构帧不发送**：`{hex, length}` | 422 |
| GET | `/expect_rules` | — | 应答预期规则库（REQS-0027）：`{version, source, deny_codes, timeout_tiers{default 5s/single_read 59s/batch_read 99s/resend_intervals_ms}, rules[], no_expect_afn}` | 200 |
| POST | `/batch_read` | `{meters[12位地址], max_concurrent=5, mode=single\|batch, protocol_type=2, timeout?, profile?, port?}`（REQS-0027 G5 滑窗任务） | 任务快照 `{job_id, meters_total, max_concurrent, timeout, in_flight, queued, done, success, failed, deny_breakdown, finished, rows[]}` | 422 / 409 |
| GET | `/batch_read`；GET `/batch_read/{job_id}`；POST `/batch_read/{job_id}/stop` | — | 任务列表 / 单任务快照 / 停止（快照结构同上） | 404 |
| GET | `/readings` | `source?（batch\|snapshot\|report）, result?（success\|deny\|timeout\|error）, since?, limit` | 统一抄读表格（G4）：`{stats{sent,replied,success,failed,success_rate,deny_breakdown}, rows[]}`；口径：超时计失败 | 200 |
| GET | `/report_buckets` | `limit` | 主动上报分桶（G6）：`{buckets{F1..F5, F5_power 停复电}, total}` | 200 |
| GET | `/frames` | `session_id?, direction:tx\|rx?, updown:up\|down?, afn?, fn?, kind?, run_id?, after_seq, limit≤500` | **`{session_id, entries[], next_after_seq, matched_total, has_more, counts{tx,rx,uplink}}`** —— 列表键是 `entries`（2026-08-31 b7647ab 前端曾误读 `frames` 键致卡"加载中"） | 404 无会话 |
| GET | `/session` | — | `{current, sessions[]}`（sc-* 帧日志会话，落盘 data/logs/simcon/） | 200 |

## 6. AI 任务门面 v2（默认 AI 调用面）

v2 将“查状态、并行观察、模块动作、验证、烧录、取证”收敛为任务级工作流。AI
客户端默认只需要发现能力、提交一个任务、读取 job、按需取证四类调用；底层
v1 路由仍保留给专家诊断和兼容场景，不通过删除 v1 来减少库存。

**访问边界**：本机请求只有在真实对端为 `127.0.0.1`/`::1` 且显式设置
`WORKBENCH_LOCAL_FULL_ACCESS=1` 时进入 `local_full`，仍会写审计；局域网请求
必须使用 Bearer grant，并按 capability、scope 和逻辑资源 alias 过滤。管理员发放
或撤销 grant 仍要求本机 + `X-Workbench-Admin-Key`。

| 方法 | 路径 | 请求 schema | 响应 schema | capability | 说明 |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/ai/v2/capabilities` | — | `CapabilitySnapshot` | `capabilities.read` | 能力、后端健康和逻辑资源别名；不泄漏 token、物理串口或绝对路径 |
| POST | `/api/ai/v2/investigations` | `InvestigationRequest` | `JobEnvelope` | `investigations.create` | 最多 3 个观察并行编排模块日志、侦听台、simcon |
| POST | `/api/ai/v2/verification-runs` | `VerificationRunRequest` | `JobEnvelope` | `verification_runs.create` | 复用现有 simcon 验证；结果不是烧录成功的替代 |
| POST | `/api/ai/v2/module-actions` | `ModuleActionRequest` | `JobEnvelope` | `module_actions.*` | 显式 `ensure`/`send`/`stop`，禁止任意 action 透传 |
| POST | `/api/ai/v2/flash-jobs` | `FlashJobRequest` | `JobEnvelope` | `flash_jobs.create` | 复用既有烧录控制；固件路径必须在授权 `firmware_roots` 内 |
| GET | `/api/ai/v2/jobs/{job_id}` | — | `JobEnvelope` | `jobs.read` | 读取统一 job；`wait_seconds=0..30` 不会因 GET 产生副作用 |
| POST | `/api/ai/v2/jobs/{job_id}/cancel` | — | `JobEnvelope` | `jobs.cancel` | 观察等可取消任务；烧录/验证拒绝取消 |
| GET | `/api/ai/v2/jobs/{job_id}/evidence` | — | `EvidenceView` | `jobs.evidence.read` | `level=L1|L2|L3`；L1/L2 有界，L3 只返回稳定引用 |

v2 的请求和响应使用命名 Pydantic schema；写任务携带 `client_request_id` 实现幂等。
`JobEnvelope.job_state` 与业务 `verdict` 分离：模块动作/烧录成功不伪装成
`pass`；观察支持 `pass/fail/inconclusive/error`。历史日志必须保留 `index_id`；
实时 `not_seen` 且无可信到达时间只能返回 `inconclusive`（`live_window_unverified`）。

### 6.0.1 侦听台分层证据与既有解析复用（REQS-0022）

侦听台默认解析已能表达「帧类型、NID、源→目的、信道、长度、状态」，通信流关联由
既有 `TraceService` 负责，分钟采集由既有 `minute_reports` 负责。AI v2 **只做适配与
投影**，不新建第二套搜索服务、不新增 `business_kind`、不改 `frames` / `minute_reports`
表结构。

`POST /api/ai/v2/investigations` 的 listener observation 支持两种 `match.kind`：

| kind | 内部实现 | 说明 |
| --- | --- | --- |
| `trace_query` | 既有 `TraceService.run_replay` | 并发抄表、单表、00A1、0020、0008 一律走这条 |
| `minute_periods` | 既有 `list_task_minute_periods` | 分钟采集；**禁止通过 raw HEX 猜测** |

```json
{
  "source": "listener",
  "target": {"index_id": "idx-20260630-a"},
  "window": {"mode": "time_range", "start": "00:00:00.000", "end": "00:05:00.000"},
  "match": {
    "kind": "trace_query",
    "scope": "round",
    "feature": {
      "app_id": "0003", "msg_seq": "1EC2", "frm_type": "终端主动并发抄表",
      "dst_tei": "087", "nid": "00947F69", "channel": "载波",
      "app_raw_contains": "123456789012", "raw_hex_contains": "123456789012"
    },
    "directions": ["downlink", "uplink", "ack"]
  },
  "completion": {"match_count": 1}
}
```

- `directions` 只做 L2 展示与计数筛选；同一通信流默认**保留必要 ACK 和对端帧**。
- `raw_hex_contains` 对整帧 `raw_hex` 验证，`app_raw_contains` 对已解析应用载荷验证。
- 全帧 HEX 条件（`raw_hex_contains`）**仅作为**既有 `app_id`、NID、时间窗或帧 ID 窗口
  收窄后的末端验证；删除空白后必须为偶数个十六进制字符、长度 2–512；
  **没有任何收窄条件时返回 422**。

`GET /api/ai/v2/jobs/{job_id}/evidence` 三级的 listener 投影：

| 级别 | 内容 | 上限 |
| --- | --- | --- |
| L1 | `index_id`、时间窗、过滤器、总帧数、按帧类型/方向计数、通信流组数、`correlation_status`、解析后端、可下钻 refs；**不含完整帧** | 3 KiB |
| L2 | `index_id`、`frame_id`、`log_time`、`FrmType`、NID、`SRC`、`DST`、`ORI_S`、`ChType`、`APP_ID`、`msg_seq`、`flow_dir`、`meter_addrs`、HEX 命中片段、分钟采集 `freeze_time` / `response_result`、ref | 16 KiB 且 ≤50 条 |
| L3 | 仅对同一 job 的 `ref=listener:<index_id>:<frame_id>` 调用既有 `get_index_frame`，返回 `raw_hex`、`summary`、`parse_error`、`analysis` 和 trace 链接 | 每次 ≤10 个 ref；无关 ref 403、格式错 422 |

铁律：

- `sequence` 是日志采集序号，**不能作为协议关联键**；多中转关联只用同一 `index_id`
  内的 `app_id + msg_seq + NID + 时间簇`。无 `msg_seq` 的帧标记
  `correlation_status=unavailable`。
- 分钟采集的业务归属**以 `freeze_time` 为准**，L2 同时给出 `log_time` 与 `freeze_time`。
- `parse_backend=none` 时保留索引和原始帧查询，缺解析字段返回 `parse_unavailable`，
  **不得把未解析帧归入并发抄表或分钟采集**。
- 全部三级必须保持同一历史 `index_id`；跨 index 禁止关联。

兼容分层与自动核对：

| 层 | 路径 | 用途 |
| --- | --- | --- |
| `v2_task_facade` | `/api/ai/v2/*`（8 条） | AI 默认低 token 任务流 |
| `v1_expert_compat` | `/api/ai/v1/*` | 既有专家操作、细粒度诊断和旧客户端兼容 |
| `workbench_legacy_orchestration` | 其余 `/api/*` | 页面、CLI 和既有编排能力 |

每次路由或 schema 变化后运行：

```bash
python tools/scripts/verify_api_inventory.py
python tools/scripts/verify_api_inventory.py --json
```

该检查只构造带惰性 stub 子应用的 OpenAPI，不打开串口、不启动侦听台、不执行真实烧录。

## 6.1 AI 控制面 v1（专家兼容层；默认 AI 不再从这里起步）

**鉴权模型**：
- 所有业务接口需 `Authorization: Bearer <token>`；token 由人经 `POST /admin/grants` 签发（仅 127.0.0.1 + `X-Workbench-Admin-Key` 请求头）。
- 每接口校验 **scope + resource**；401 无/坏 token，403 越权，409 占用/幂等冲突，503 后端未挂载，422 请求体非法。
- 长任务（flash/observation/trace/simcon verify）返回 `operation_id`，轮询 `/operations/{id}/wait?timeout_seconds≤30` 到终态。
- 幂等：`client_request_id`（或 `Idempotency-Key` 头）重复提交返回既有操作。
- 烧录强制白名单：`bin_path` 必须在授权的 `firmware_roots` 内，否则 403。

| 方法 | 路径 | scope | 说明 |
| --- | --- | --- | --- |
| GET/POST | `/admin/grants` | admin key | 列出 / 签发授权（201，返回 `{grant, token}`，token 仅此一次） |
| POST | `/admin/grants/{grant_id}/revoke` | admin key | 撤销（404） |
| GET | `/status` | `status:read` | 全局状态快照（含 evidence:read 才带路径） |
| GET | `/audit` | `status:read` | `{entries:[审计流水]}`（按授权 resources 过滤） |
| POST | `/module-sessions/ensure` | `module_session:ensure` | 确保会话存在 |
| POST | `/module-sessions/{id}/stop` | `module_session:stop` | 停会话（force 可选，409/503） |
| POST | `/module-sessions/{id}/send` | `module_send:execute` | 发送数据（幂等） |
| POST | `/flash-operations` | `module_flash:execute` | 烧录（202 → operation） |
| POST | `/listener/ensure` | `listener:ensure` | 确保侦听台采集就绪 |
| POST | `/listener/stop` | `listener:stop` | 停止采集（409/503） |
| POST | `/observations` | `observation:create` | 建观察任务（202；`Idempotency-Key` 支持） |
| GET | `/operations/{id}`、`/{id}/wait`、POST `/{id}/cancel` | `evidence:read` / `observation:create` | 查询 / 等待 / 取消操作 |
| GET | `/artifacts/{id}`、`/{id}/content` | `evidence:read` | 证据清单 / 内容 |
| GET | `/listener/schema` | `evidence:read` | 侦听台数据 schema |
| POST | `/listener/traces` | `listener:trace` | 建追踪（202 → operation；幂等） |
| GET | `/listener/traces`、`/listener/traces/{id}` | `evidence:read` | 追踪列表 / 快照 |
| GET | `/listener/indexes`、`/{id}/frames`、`/{id}/frames/{frame_id}` | `evidence:read` | 帧索引查询（参数同 §3.2） |
| POST | `/simcon/verify` | `simcon:verify` | 验证任务（202 → operation；409 占用） |
| POST | `/simcon/step` | `simcon:send` | 单步下发（422/409） |
| GET | `/simcon/frames` | `simcon:read` | 帧日志查询（过滤器同 §5，返回 `entries` 键） |
| GET | `/simcon/session` | `simcon:read` | 当前会话 |
| POST | `/simcon/open`、`/simcon/close` | `simcon:send` | 开/关串口 |

scope 全集：`status:read, module_session:ensure, module_session:stop, module_send:execute,
module_flash:execute, listener:ensure, listener:stop, listener:trace, observation:create,
evidence:read, simcon:verify, simcon:send, simcon:read`。

## 7. 编排（`/api/*`，workbench 自身；CLI / REST / AI 三端复用）

| 方法 | 路径 | 说明 | 状态码 |
| --- | --- | --- | --- |
| GET | `/api/scenarios` | 场景模板清单 | 200 |
| GET | `/api/scenarios/{scenario_id}` | 单个场景（含校验） | 404 / 422 |
| GET | `/api/scenarios/{scenario_id}/task` | 场景激励任务原始 JSON（stimulus.task_file） | 404 未声明/文件缺失 / 422 越出目录 |
| POST | `/api/run` | 创建并异步执行验证批次（RunRequest）；返回 canonical run 视图，轮询 GET | 404 / 500 |
| POST | `/api/run/{run_id}/cancel` | 协作式取消 | 404 / 409 |
| GET | `/api/run/{run_id}` | run 状态（终态 passed/failed/cancelled/error/inconclusive） | 404 |
| GET | `/api/run/{run_id}/report` | canonical 报告 | 404 |
| GET | `/api/run/{run_id}/artifacts` | artifact manifest 清单 | 404 |
| GET | `/api/run/{run_id}/artifacts/{artifact_id}` | 按逻辑 ID 下载产物（路径越界防护） | 404 |
| GET | `/api/runs?limit≤200` | run 列表 | 200 |
| POST | `/api/compare` | `{expected_flow, events}` → 比对结论（不落 Run） | 200 |
| POST | `/api/feedback` | `{flow_compare, simcon_summary, loghooks_drift}` → 反馈归因 | 200 |

## 8. 协议字典（`/api/dict`，只读；数据源自 libs/ 真实文件，simple JSON 键即事实契约）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/dict` | 字典清单 `[{id:oad|di|afn-fn|rules|cases, name, count, path, desc}]` |
| GET | `/api/dict/oad?q=` | 698.45 OAD 字典（模糊过滤键/名称/描述） |
| GET | `/api/dict/di?q=` | 645-2007 DI 字典 |
| GET | `/api/dict/afn-fn?q=` | 1376.2 AFN/Fn（`{items, fn_count, source, note}`） |
| GET | `/api/dict/rules?q=` | loghooks 事件规则（`{files:[{file,count,entries}]}`） |
| GET | `/api/dict/cases?category=&type=&q=` | 检测用例库（REQS-0025）：`{count, declared_total:269, categories, items}`；category 过滤分类、type=case\|param_table、q 模糊过滤 |
| GET | `/api/dict/cases/{entry_id}` | 单条用例/参数表行（404 不存在）；字段含 purpose/frames/steps/criteria/source（doc+distill+section 可追溯） |

## 9. 串口 Profile（`/api/serial-profile`）

| 方法 | 路径 | 请求体 | 响应要点 | 状态码 |
| --- | --- | --- | --- | --- |
| GET | `/api/serial-profile` | — | `{profiles{四槽}, slots}` | 422 配置损坏 |
| PUT | `/api/serial-profile` | `{profiles:{slot:{mapping_id, enabled, baudrate, parity, bytesize, stopbits}}}` | `{saved:true, profiles}` **只保存不碰硬件** | 422 未知映射/非法 |
| POST | `/api/serial-profile/apply` | —（只读已保存版本） | 应用结果（module/listener/simcon 槽） | 503 应用器未配置 |

---

## 10. 前端调用方映射（页面 → API 组 → 前缀机制）

| 前端文件 | 调用组 | 前缀机制 |
| --- | --- | --- |
| `apps/workbench/static/pages/listener/{app,frames-pro}.js` | §3（日志/帧/串口/fs） | **硬编码** `/api/listener/...`（独立版 `apps/listener/static/` 同逻辑硬编码 `/api/...`，两副本并存） |
| `pages/trace/trace.js` | §3.5 + `/api/listener/logs/frames/{id}`、`/api/listener[/listener]/indexes` | 硬编码，注意双前缀 |
| `pages/dict/dict.js` | §8 | 硬编码 `/api/dict` |
| `pages/scenario/scenario.js` + `workbench.html` | §7 | 硬编码 `/api/...` |
| `pages/simcon/simcon.js` | §5 + `/api/dict/afn-fn`（构帧预览字典） | 硬编码 `/api/simcon` |
| `pages/module-serial/module-serial.js`（两副本） | §4 + `/fs/*` + `/loghooks/*` | `API_BASE = body[data-api-base] ?? "/api"` ＋ 路径自带 `/module-serial` 命名空间 → 两部署形态通用 |
| `pages/serial-profile/serial-profile.js` | §9 | `API_BASE`（`/api`） |
| `apps/module_log/static/module-serial.js` | 同上（独立版） | 同机制（8766 直连） |
| AI agent（无页面） | §6（默认）/§6.1（专家兼容） | 默认直连 8790 `/api/ai/v2`；需要旧细粒度能力时使用 `/api/ai/v1` |

## 11. 契约红线（开发/检查清单）

1. **改任何路由/字段：先改后端 → 同步本文件 → 跑 `apps/workbench/test_*.py` 契约测试**。
2. **双前缀特例**：workbench 下 listener 的 traces/indexes 是 `/api/listener/listener/*`；别"顺手修正"成单前缀。
3. **双副本同步**：页面在 `apps/<pkg>/static/`（独立版）与 `apps/workbench/static/pages/<pkg>/`（嵌入版）**必须同时存在**（workbench 只挂自己的 static）。改 JS/CSS 两份都要改并**同一 commit 提交**——一键启动用 `git archive HEAD`，未提交的改动不生效。
4. **simcon 帧列表响应键是 `entries`**（含 `counts/next_after_seq/has_more`），不是 `frames`。
5. **异步端点返回 202 + 轮询**：logs/open、serial/start、module-serial start/flash、AI flash/observation/trace/simcon-verify、POST /api/run。前端必须实现轮询与取消。
6. **409 是资源冲突**（串口占用/互斥），不是错误——UI 应提示而非报错弹窗。
7. 字典/规则端点数据来自 `libs/parser_lib/adapters/*/metadata/*.json` 与 `libs/loghooks/rules/`，**改 JSON 即改端点输出**（无拷贝层）。
8. AI 控制面：新接口必须声明 scope；烧录类必须走 firmware_roots 白名单；幂等键 `client_request_id` 全程携带。
9. v2 是默认低 token 任务入口；v1 保持专家兼容，不得因库存收敛而删除或改名。
10. 主题（REQS-0012）：`html[data-theme]` + `--theme-registry` 单一数据源；新增主题只改 `tokens-v2.css` 一处；iframe 内页面需带防闪跳 boot 脚本与 `wb-theme-change` message 监听（见 §12 已知缺口）。

## 12. 已知缺口（2026-08-31 前端改动审核产出；G1/G2 已于同日修复）

> 修复记录：G1 = `var body` 上移到空态分支之前；G2 = 六页（trace/dict/scenario/simcon/
> listener/workbench）`<head>` 补 `wb-theme-change` message 监听（写法对齐 module-serial 页）。
> 至此 9 个保活子页全部具备主题实时跟随。下表保留作审核记录。

| # | 缺口 | 位置 | 影响 | 修法 |
| --- | --- | --- | --- | --- |
| G1 | `refreshFrames` 空结果分支 `var body` 声明在使用之后（var 提升为 undefined），`body.querySelector` 抛 TypeError 被静默 `.catch` 吞掉 | `apps/workbench/static/pages/simcon/simcon.js:271-277`（b7647ab 引入） | 空会话/过滤无结果时列表停在"加载中…"，不会显示"暂无帧记录"——与该 fix 想修的症状同源，空会话场景仍复现 | 把 `var body = $("#trBody")` 上移到 `if (!frames.length)` 之前 |
| G2 | 保活 iframe 切主题不实时跟随：外壳 `switchTheme` 会向所有 iframe `postMessage({type:"wb-theme-change"})`，但只有 module-serial / maintenance / serial-profile 三页装了 message 监听 | `pages/trace|dict|scenario|simcon` 及 `pages/listener/index.html`、`workbench.html`（reqs/0010 落地时即缺，非 0012 回归；maintenance 同款根因已在 REQS-0012 P5 修过 3 页） | 主题切换后，已打开的这些页签保持旧主题，直到页面重载 | 各页 `<head>` 防闪跳脚本里补 `window.addEventListener("message", e => e.data?.type==="wb-theme-change" && 注册表校验通过则 dataset.theme=...)`，参考 `pages/module-serial/module-serial.html:35-41` |

（其余主题遗留见 `reqs/0012-workbench-theme-refactor/OVERVIEW.md` §五 L1/L2/L3，均有记录，不重复。）
