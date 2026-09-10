# 项目支持功能清单

> 整理日期：2026-08-31；基线：master（REQS-0010 页面落地 + REQS-0012 主题重构完成后）。
> 事实来源：后端路由代码与页面，逐条核对记录见 `docs/api-contract.md`——本文只记"有什么功能"，
> 接口字段/状态码细节不在此重复。**维护约定：新增或下线功能必须同步本文件；接口层变化同步 api-contract.md。**

## 1. 统一工作台外壳（8790，`apps/workbench/static/`）

| 功能 | 说明 |
| --- | --- |
| 页签导航 + hash 路由 + iframe 保活 | 首载后只切 `hidden`，子页状态不丢失；数据驱动导航（PAGES/GROUPS） |
| 双主题切换 | 墨夜 midnight / 晴昼 daylight；`--theme-registry` 单一数据源（tokens-v2.css），9 个保活子页经 `wb-theme-change` 实时跟随（REQS-0012） |
| 子系统健康探测 | 页脚显示 module_log / listener 挂载状态（`GET /api/platform-version`）；挂载失败降级不拖垮整体 |
| 防主题闪跳 | 各页 `<head>` 内联 boot 脚本，registry 白名单校验 |

## 2. 侦听台（listener，独立版 8765 / 工作台 `/api/listener/*`）

| 功能 | 关键端点（workbench 外部路径） | 备注 |
| --- | --- | --- |
| 日志文件索引（异步） | `POST /api/listener/logs/open`(202) → `logs/status` 轮询 | 与串口采集互斥（409） |
| 帧分页浏览 + 深度解析 | `GET /api/listener/logs/frames`（offset/limit/query/nid/时段/after_id 增量）、`logs/frames/{id}` | 解析依赖 GwHPLCAnalysis.dll，缺失时 /parse 降级 503，采集/索引不受影响 |
| 多索引库管理 | `GET /api/listener[/listener]/indexes…`（双暴露，见契约 §3.2） | |
| 分钟采集分析 | `logs/minute-analysis`、`logs/delete-config-details` | |
| 任务报文分析 | `logs/task-config-tasks/summary/lifecycle`、`task-minute-analysis`、`task-derived-period` | |
| 网络承载评估 | `network/assessment`（完整）/ `network/status`（AI 轻量快照 ≤1KB，healthy/degraded/fault） | 无信标时 fallback=beacon_undetected |
| 串口实时采集 | `serial/ports·status·start`(202)·`stop` | 落盘 data/logs/侦听台/ |
| 组网观测（REQS-0024/0026） | `network/events`、`network/digest`、`network/events/{id}/brief`、`network/overview`、`network/beacons` | 4-2 链路层/NWK 组网事件流（三级分级 alarm/watch/normal + TEI→表号人话翻译）+ 印象结论 digest（≤4KB：一句话判定+异常清单+自适应时间桶）+ 点击行按需单帧粗略解析 brief（≤2KB）；页面「组网观测」页签：结论卡/时间桶定点排查/降噪事件表/行内解析面板；卡片只留事件侧统计（信道质量归评估页，评估页异常周期可下钻）；首次调用触发增量扫描落 nwk_events 表（含 level 列自动迁移） |
| 通信流追踪（需求 0009/ADR-9） | `POST/GET/DELETE /api/listener/listener/traces…`（**双前缀**） | 三段证据链 S1 发出→S2 ACK/响应→S3 接收，回放 + live |
| 新版帧浏览 | frames-pro 页签 | `feature_hint` 一键反推追踪特征草稿 |

## 3. 模块日志 / 烧录（module-serial，独立版 8766 / 工作台 `/api/module-serial/*`）

| 功能 | 关键端点 | 备注 |
| --- | --- | --- |
| cco/sta 双通道动态会话 | `sessions` CRUD、`/start`(202)、`/stop`、`/write`、`/write-text`、`/baudrate`、`/logs?after` | 新前端与 AI 共用 |
| 固件上传 + xmodem 烧录 | `POST upload`（base64 ≤10MB）、`sessions/{id}/flash`（slot 0-1/baud_plan） | |
| loghooks 事件对照解析 | `/api/loghooks/scan·realtime·sources`（`/api/module-serial/loghooks/*` 双暴露） | 事件名即场景 expected_flow 的 event_type |
| 旧双通道 API（兼容） | `start/stop/write/write_text/baudrate/flash/logs`（带 channel） | |
| 前缀注入 | 页面 `data-api-base` + 路径自带命名空间 | 两种部署形态同一份 JS |

## 4. 模拟集中器（simcon，独立版 8781 / 工作台 `/api/simcon/*`）

| 功能 | 关键端点 | 备注 |
| --- | --- | --- |
| 串口自动选择 | `POST open` / `close` | **无固定映射**：不传 port 自动选可用串口（9600/E/8/1），显式 port 覆盖 |
| 验证任务 | `POST verify` | 多步 + 应答器，逐步判定 + summary.verdict |
| 单步下发 / 感知主动上报 | `POST step` | ADR-5 语义化（send 只写 afn/fn+params）；REQS-0027：auto_expect 自动生成 expect + per-Fn 超时档位（5s/59s/99s）+ 否认码人话 + 旁听帧归类 |
| 应答预期规则库 | `GET expect_rules` | AFN/Fn→应答形态映射、否认码 6D/6E/6F 语义、超时档位声明（蒸馏出处标注） |
| 并发抄表滑窗 | `POST batch_read`、`GET batch_read/{id}`、`POST …/stop` | 最大并发可配；回一帧补一发保持在途=最大并发；应答/否认/超时均释放槽位 |
| 统一抄读表格 | `GET readings` | 单抄/并抄/快照/上报共用一表；成功率统计 + 否认码细分 + 来源/结果筛选 |
| 上报分类型计数 | `GET report_buckets` | 06H F1-F5 各桶；停复电（协议类型 04H）单独一表 |
| 语义构帧预览 | `POST build` | 只算不发（scenario_codec），UI 帧预览 |
| 会话帧日志 | `GET frames`（**entries 信封** + 游标翻页）、`GET session` | 持久化 data/logs/simcon/sc-*.jsonl |
| 内置应答规则 | `GET responders` | |
| 页面 | 模拟集中器页（收发记录 2.5s 轮询、构帧预览调 `/api/dict/afn-fn`） | |

## 5. 协议字典（`/api/dict`，只读）

| 功能 | 端点 |
| --- | --- |
| 字典清单 | `GET /api/dict` |
| 698.45 OAD / 645 DI / 1376.2 AFN-Fn / 事件规则 | `GET /api/dict/{oad,di,afn-fn,rules}?q=` 模糊过滤 |
| 检测用例库（REQS-0025）：269 项体系可枚举条目 + 检测线抄控器 + 河南流水线 + 测试/安全模式参数表 | `GET /api/dict/cases?category=&type=&q=`、`GET /api/dict/cases/{entry_id}` |
| 数据源 | `libs/parser_lib/adapters/*/metadata/*.json` + `libs/loghooks/rules/` + `libs/case_library/data/cases.json`（generate.py 再生成）——**改 JSON 即生效**（无拷贝层） |
| 页面 | 协议字典页（第 5 本字典卡 + 分类下拉） |

## 6. 验证编排（`/api/*`，CLI / REST / AI 三端复用）

| 功能 | 端点 | 备注 |
| --- | --- | --- |
| 场景模板 | `GET /api/scenarios[/{id}][/task]` | 激励任务原始 JSON（reqs/0010 P3） |
| Run 全链路异步执行 | `POST /api/run` → 轮询 `GET /api/run/{id}` → `report` / `artifacts` 下载 / `cancel` | 烧录→监控→激励→比对→反馈→报告；终态 passed/failed/cancelled/error/inconclusive |
| Run 历史 | `GET /api/runs?limit` | |
| 直接比对 / 反馈归因 | `POST /api/compare`、`POST /api/feedback` | 不落 Run |
| 已知缺口 | join_anhui / open_close / search_meter 三个场景 tasks/*.json 缺失 | 端点 404 明确报错，页面红条提示 |

## 7. 串口 Profile（`/api/serial-profile`）

| 功能 | 端点 | 备注 |
| --- | --- | --- |
| 四槽配置保存 | `GET / PUT` | **只存不碰硬件** |
| 一键应用 | `POST /apply` | module / listener / simcon 三槽适配器；只读已保存版本 |

## 8. AI 控制面（`/api/ai/v1`，供外部 AI agent）

| 能力 | 端点组 | 说明 |
| --- | --- | --- |
| 授权体系 | `admin/grants`(201)、`…/revoke`、`GET /audit` | 仅 127.0.0.1 + admin key；13 种 scope、资源粒度、固件目录白名单、ttl；token 只显示一次 |
| 全局状态 | `GET /status` | workbench / listener / 会话 / 活跃操作 / 串口句柄快照 |
| 模块会话 | `module-sessions/ensure·{id}/stop·{id}/send` | 幂等（client_request_id） |
| 烧录 | `POST flash-operations`(202) | 强制 firmware_roots 白名单（403） |
| 观察任务 | `POST observations`(202) | 5 种 matcher（literal/regex/loghook_rule/sequence/not_seen）× 3 种窗口（live/time_range/cursor_range）；先建观察再制造事件 |
| 操作与证据 | `operations/{id}[/wait·/cancel]`、`artifacts/{id}[/content]` | wait 轮询到终态，artifact 即取证 |
| 侦听台控制/查询 | `listener/ensure·stop`、`listener/schema`、`listener/indexes…`、`listener/traces…` | 通信流追踪 202 → operation → result.report |
| 侦听台语义查询与分层证据（REQS-0022） | v2 `investigations` 的 `match.kind=trace_query`（复用 TraceService）/ `minute_periods`（复用 list_task_minute_periods）；`jobs/{id}/evidence?level=L1\|L2\|L3` | L1 摘要 ≤3KiB 无 raw_hex；L2 解析投影 ≤16KiB/50 条；L3 同 job `ref=listener:<index_id>:<frame_id>` 回传完整帧（越权 403/格式错 422） |
| 模拟集中器 | `simcon/verify·step·frames·session·open·close` | resource 固定 simcon，帧列表 `entries` 键 |
| 使用文档 | `.agents/skills/ai-control-plane/SKILL.md`（v2.0.0：路由器 + references 按需加载）+ `docs/16-AI操作指南.md` | 错误码语义 401/403/404/409/422/503 见技能主文件 |

## 9. 支撑工具链

| 工具 | 位置 |
| --- | --- |
| 一键启动（`git archive HEAD`，**未提交的改动不生效**） | `tools/scripts/` |
| 一键生成 AI 密钥 | `tools/scripts/一键生成AI密钥.bat` |
| 73 Fn 全量构帧验收清单生成器 | `tools/scripts/build_all_frames_txt.py` |
| 主题覆盖率门禁 | `reqs/0012-workbench-theme-refactor/verify-theme-coverage.js` + pytest |
| 契约测试 | `apps/workbench/test_*.py`（外壳导航/串口 Profile/AI 控制面等）、`apps/module_log/test_*.py` |

## 10. 关联文档

| 文档 | 内容 |
| --- | --- |
| `docs/api-contract.md` | 接口契约总表（路由/参数/响应键/状态码/前缀映射/契约红线） |
| `docs/16-AI操作指南.md` | AI 控制面完整操作手册 |
| `.agents/skills/ai-control-plane/SKILL.md` | AI 控制面执行步骤（v2.0.0：路由器 + references 按需加载） |
| `REQS-INDEX.md` / `DECISIONS.md` | 需求索引 / ADR 决策记录 |
