---
name: ai-control-plane
description: Control the HPLC meter-reading workbench over HTTP as an AI, plus an offline app-layer frame toolkit. Frame parse/build/verify (1376.2 nesting 698/645, e.g. 1103 concurrent meter reading) works WITHOUT the workbench via the daily lightweight path; the bounded task facade at /api/ai/v2 covers low-token investigations, module actions, verification, flashing, jobs, and evidence; /api/ai/v1 is retained for expert diagnostics and legacy clients. Use when an AI agent needs to parse/build/verify protocol frames offline or operate the 侦听台改造 workbench (serial ports, flash, log observation, evidence retrieval) programmatically, e.g. "解析这帧 68 开头的报文"、"构一帧 645 读电能"、"用 AI 控制台向 cco/sta 发串口指令"、"AI 烧录固件并等结果"、"AI 观察日志并取证".
argument-hint: "[task, e.g. 解析这帧报文 / 构一帧645读电能 / 监控cco日志直到出现XX / 烧录固件]"
metadata:
  author: reasonix
  version: "2.6.0"
  applies-to: /01-workfile-ai/01-zzt/ZZT_SELF（WSL 权威仓库；Windows 侧见 D:\2-侦听台改造，解析网关明文区部署另见 D:\019-wy-tool\ZZT_SELF）
  source: 工作台仓库 .agents/skills/ai-control-plane（事实源，改动先改此处再回灌全局）
---

# AI 控制面 Skill（ai-control-plane）

**先按用途路由（渐进式加载）：帧解析/构帧/回验 → 直接用下方「日常轻量档」，无需工作台；
需要驱动工作台时，默认按任务走 v2 最小路径：先发现能力，提交一个
任务，读取 job，按需取证；只读对应 reference，用完即止。** v2 不删除 v1；八步细节
在下方 v1 references/*.md，完整手册为 `references/operation-guide.md`（自包含副本）。
**例外**：下表「离线数据排查 / 漏点定位」是组合场景，允许一次读
`offline-analysis.md` + `cco-log.md` + `listener.md` 三个 reference（多端交叉验证需要）。

## 用途路由（渐进式加载：先看本表，只读所需，用完即止）

| 当前用途 | 读什么 | 不必读 |
| --- | --- | --- |
| **用户给了帧要解析 / 要构帧 / 产帧要回验（TDD）** | **下方「日常轻量档」即可独立完成** | 全部 v1/v2 references |
| 发现后端/逻辑资源、并行观察、取证 | v2 门面速查（下表） | 全部 v1 references |
| 监控日志 / 盯帧取证 | references/observations.md | 其余 |
| 发串口指令 / 烧录固件 | references/module-serial.md | 其余 |
| 验证用例 / 单步 / 查帧 | references/simcon.md | 其余 |
| 查已解析帧 / 业务流追踪 | references/listener.md | 其余 |
| 组网排查（入网/离网/冲突/信标） | references/network-diagnostics.md | 其余 |
| 离线数据排查 / 漏点定位 | offline-analysis.md（组合场景 +cco-log +listener） | 其余 |
| 全链路场景 / 字典查询 / 8790 构帧预检 | references/helpers.md | 其余 |
| 拿 token / 管授权 | references/auth.md（人来做） | 其余 |

## 日常轻量档（应用层帧工具，免工作台，REQS-0032）

> 适用：手头只有一帧报文要解析，或按知识库帧格式构帧做测试用例（TDD）、产帧要验收。
> **不启工作台 8790、不启解析网关 8700、不需要 DLL / token / 串口**——
> 纯 Python 解析库 `libs/parser_lib` 直用，JSON 打到 stdout。

- **覆盖范围**：应用层帧 = **1376.2（内嵌 698/645 自动递归解出，典型如 1103 并发抄表
  F1H-F1）、698.45、645-2007**。GW 封装/双模/网络层帧不在日常档（走上方全功能档）。
- **双模式容错**：不指定协议 = 自动嗅探（严格：校验和参与打分，识别不了输出
  `unrecognized` + 各协议得分 + 建议指定协议重试，**不硬解**）；`--protocol` 指定 =
  宽容（**允许错误帧**：强制解析，CS/FCS 校验失败以 `warnings` 表达）。
- 仓库根 `<WORKBENCH_ROOT>` 解析见下一节（启动器已自动注入 sys.path，免配 PYTHONPATH）。

```bash
# 1) 解析：hex → JSON（自动嗅探；1376.2 内嵌 645/698 进 frame.nested）
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py parse --hex "68 12 34 ..."
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py parse --hex "<错帧>" --protocol 645  # 指定=强解+warnings

# 2) 构帧：语义参数 → 帧 hex（1376.2 透传 adapter_10376.build_frame_json 全量契约）
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py build --protocol 645 \
  --params '{"addr":"123456789012","control":"11","di":"00010000"}'
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py build --protocol 698.45 \
  --params '{"addr":"05353781090030","ca":"00","oad":"02010200"}'
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py build --protocol 1376.2 \
  --params '{"afn":"F1","fn":1,"data":{"raw":"<645/698帧hex，1103包裹场景>"}}'

# 3) 回验：解析回验 + 意图字段比对（构帧产物 TDD 断言依据；verified=false 时看 diff）
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py verify --hex "68 ..." \
  --expect '{"地址域":"123456789012"}'
```

- 退出码：0 = 成功（verify 需 `verified:true`）；1 = 业务失败（JSON 内 `error` /
  `verified:false`，含"无法识别"）；2 = 用法错误。
- 库级 API（在脚本里 import）：`PYTHONPATH=libs` 后
  `from parser_lib.facade import decode, build, verify`；单测样例见
  `libs/parser_lib/test_facade.py`（含 1103 并发抄表构帧样本）。
- 与全功能档的关系：真实下发/串口/烧录/取证仍走 v2/v1；8790 的 `POST
  /api/listener/parse`（net48 DLL 深度解析）与本轻量档口径不同源，做对拍时才一起用。

## 路径根解析（全局可用前提）

- `references/`、`scripts/`、`使用经验/` **相对本技能目录**——直接存在，无需外部依赖。
- `apps/`、`docs/`、`tools/`、`data/`、`.build_plain/`、`DECISIONS.md` **相对工作台仓库根
  `<WORKBENCH_ROOT>`**：权威路径 `/01-workfile-ai/01-zzt/ZZT_SELF`（WSL），Windows 侧
  `D:\2-侦听台改造`；深读源码/决策前先向用户确认仓库路径，或按
  `scripts/verify_api_inventory.py` 的候选列表探测。
- 校验脚本 `scripts/verify_api_inventory.py` 已内置仓库根解析：`--repo-root` →
  `WORKBENCH_ROOT` 环境变量 → 候选路径探测；找不到时给出明确报错。只构造惰性
  stub（不开串口、不启动侦听台、不执行烧录）。

## 实测校准（2026-09-10 全链 e2e 验证，与真实接口一致）

- **investigation 信封恒为 `queued`**（即使同步历史路径已在返回前执行完）——
  创建后**必须** `GET /jobs/{id}` 读终态；`verdict` 只用于 investigation 观察
  （module_action/verification_run/flash_job 恒 null）。
- **L3 ref 格式**：`listener:<index_id>:<frame_id>`（不是 `index_id:frame_id`），一次 ≤10 个。
- **listener 历史查询**：`window.type` 仅支持 `cursor_range`，且 `mode` 必须为
  `cursor_range`（写 `historic` 实际报「window.mode 仅支持 live、time_range 或
  cursor_range」）；需 `window.index_id` +
  `start_frame_id/end_frame_id`（索引边界内，可用只读 sqlite 查
  `apps/listener/runtime/indexes/idx-*.sqlite3` 的 `frames.id` 范围）；`match.kind`
  仅 `parsed_frame`/`frame_query`。
- **token 分界**：v2 门面在 `local_full` + loopback 免 token；v1 业务端点
  （如 `/api/ai/v1/listener/indexes`）即使 local_full 也需 Bearer token。
- **module stop**：普通 stop 遇活跃观察任务返回 409（非故障）→ `force:true`；
  v2 stop job 正常一次收敛 succeeded（2026-09-14 修复，不再卡 waiting）。
- **investigation 业务参数同步校验**：非法 window.mode、缺 match、未知 session_id、
  minute_periods 缺 task_no、raw_hex 无收窄条件现在创建即 422（此前 202 后异步 error
  且无原因）；仍走异步的 error 会在 evidence L2 `data.reason` 带原因。
- **verify 总超时**：simcon verify 默认 240s 总看门狗（`WORKBENCH_VERIFY_TIMEOUT_S`
  可覆盖），超时落 `error` 并复位运行守卫——后续提交不会再被 409 永久拒绝；
  不可取消红线不变，耐心等到该终态即可。
- **烧录文件选择**：升级/烧录用 `iap_{cco|ecu}_*.bin`（IAP 串口升级镜像），**禁止用 `flash_*.bin`**
  （生产烧录整片镜像，bootloader 升级路径不认，实测 ~24% 后模块中止）；先读 `firmware/readme.txt`。
- **工作台启动**：`cd <WORKBENCH_ROOT>/apps && PYTHONPATH=apps:libs python -m workbench.run`
  （README 的 `python -m workbench.run` 隐含 apps/ 在 sys.path；直接跑会
  `ModuleNotFoundError: shared`）。

## 任务 → 最小路径速查

### v2 默认任务门面

| 任务 | 最小调用链 | 任务路径 |
| --- | --- | --- |
| 发现后端/逻辑资源 | `capabilities` | `GET /api/ai/v2/capabilities` |
| 并行观察日志/侦听台/simcon | `investigations` → `jobs/{id}` → `evidence` | `POST /api/ai/v2/investigations` |
| 发串口指令（cco/sta） | `module-actions` → `jobs/{id}` | `POST /api/ai/v2/module-actions`（action=ensure/send/stop） |
| 验证用例/单步 | `verification-runs` → `jobs/{id}` → `evidence` | `POST /api/ai/v2/verification-runs` |
| 烧录固件 | `flash-jobs` → `jobs/{id}` | `POST /api/ai/v2/flash-jobs` |
| 取消任务 | `jobs/{id}/cancel` → `jobs/{id}` | `POST /api/ai/v2/jobs/{id}/cancel` |
| 读取任务/证据 | `jobs/{id}` → `jobs/{id}/evidence?level=L1\|L2\|L3` | GET |

v2 每次写任务带 `client_request_id`；默认 `cleanup=owned_only`。`job_state` 是执行状态，
`verdict` 只用于 investigation 观察（module_action/verification_run/flash_job 恒 null）。
先取 L1 摘要，再按需升级 L2/L3，避免把底层原始日志直接
塞进 AI 上下文。历史观察保留 `index_id`；实时 `not_seen` 且无可信到达时间只能是
`inconclusive`（`live_window_unverified`）。

### v1 专家/兼容路径

| 任务 | 最小调用链 | 需读（按需，只读一个） |
| --- | --- | --- |
| 监控日志 / 盯帧取证 | `observations` → `operations/{id}/wait` → `artifacts/{id}/content` | references/observations.md |
| 发串口指令（cco/sta） | `module-sessions/ensure` → `send`（→ `stop`） | references/module-serial.md |
| 烧录固件 | `flash-operations` → `wait` | references/module-serial.md |
| 验证用例 / 单步 / 查帧 | `simcon/verify·step` → `frames` | references/simcon.md |
| 查已解析帧 / 追踪一轮业务 | `listener/indexes…/frames`、`listener/traces` | references/listener.md |
| 排查组网问题（入网/离网/冲突/心跳/信标） | `listener/network/digest`（L1 结论 ≤4KB：verdict+异常清单+时间桶）→ `network/events?level=alarm,watch`（L2 明细，锁定桶窗）→ `network/events/{id}/brief`（L3 单帧粗解 ≤2KB）；评级快照才用 `network/status` | references/network-diagnostics.md |
| 离线数据排查 / 漏点定位 | **API 优先**：`listener/minute-periods` + `simcon/store/events|snapshots`；原始日志/CCO grep 才离线直查（组合场景，读 3 个） | references/offline-analysis.md（+ cco-log.md + listener.md） |
| 跑场景全链路 | `POST /api/run` → 轮询 → report | references/helpers.md |
| 查协议语义 / 构帧预检 | `/api/dict`、`/api/simcon/build` | references/helpers.md |
| 拿 token / 管授权 | `admin/grants`（**人来做**） | references/auth.md |

## 通用约定

- Base `http://127.0.0.1:8790`；v2 默认路径为 `/api/ai/v2/*`。本机启用
  `WORKBENCH_LOCAL_FULL_ACCESS=1` 且真实对端为 loopback 时可用 v2 全能力（免 token）；
  局域网或 v1 业务接口需人签发的 `Authorization: Bearer <token>`（不要把 token 写进
  输出、日志或提交内容）。
- 探活：`GET /api/health`（免鉴权）；v2 用 `GET /api/ai/v2/capabilities` 发现能力，
  v1 专家状态用带 token 的 `GET /api/ai/v1/status`。
- v2 幂等：写操作一律带 `client_request_id`；重复提交复用原 job。v1 也支持
  `client_request_id`（或 `Idempotency-Key` 头）。
- v2 长任务返回 202 + `job_id`，用 `GET /api/ai/v2/jobs/{job_id}` 读取；v1 长任务
  返回 `operation_id`，用 `GET /api/ai/v1/operations/{id}/wait?timeout_seconds≤30` 轮询。
- 错误码：401 token 缺失/失效；403 越权/固件目录外/非本机发授权；404 资源不存在；
  **409 资源冲突（串口占用/会话冲突）不是故障**；422 参数非法；503 后端不可用/未配置。
- 侦听台深度解析三档 `parse_backend`（local/remote/none，REQS-0019）：`none` 时帧仍可查
  但无深度字段，先起 Windows 解析网关——**仅 Windows 侧、由人执行**（桌面
  `wsl环境部署.bat` → [4]，或 `powershell -File tools/scripts/uart-map.ps1 -Action
  start-gateway`，相对 `<WORKBENCH_ROOT>`；详见 references/listener.md）。

## 红线（行为边界）

1. **scope 最小化**：授权只申请本次任务需要的 scope（映射表见 references/auth.md）。
2. **用完即止**：完成本次任务即停——不开任务外的会话、不跑任务外的验证、不做"顺手"的全流程。
3. **串口独占**：同一物理串口同一时刻一个持有者（AI 与前端共享规则）；开了就关
   （stop/close 释放；v2 stop 卡 waiting 时以物理串口释放为准）；409 时等待或换口，不硬抢。
4. **观察先建后造**：先 `observations` 再制造目标事件（module_log 只盯创建之后的新日志）。
5. **授权归人**：`admin/grants` 只由人本机执行；AI 只使用已有 token，不自签、不扩权。
6. 不可取消的操作（烧录/verify）耐心等到终态，不并发重试；v2 对应
   `flash-jobs`/`verification-runs`，v1 对应 `flash-operations`/`simcon/verify`。

## 参考

- 完整操作手册（自包含）：`references/operation-guide.md`；接口契约总表：`references/api-contract.md`；功能清单：`references/features.md`
- v2 OpenAPI/库存校验（技能内，惰性 stub，不开串口/不启动侦听台/不烧录）：
  `python scripts/verify_api_inventory.py [--repo-root <WORKBENCH_ROOT>]`
- v2 实现（仓库深读，相对 `<WORKBENCH_ROOT>`）：`apps/workbench/ai_v2_api.py`、`ai_capability_service.py`、`ai_contracts.py`
- v1/共享实现（仓库深读，相对 `<WORKBENCH_ROOT>`）：`apps/workbench/ai_api.py`、`ai_operations.py`、`ai_auth.py`、`ai_store.py`
- 决策（相对 `<WORKBENCH_ROOT>`）：`DECISIONS.md` ADR-28（开放 0.0.0.0 局域网监听）
