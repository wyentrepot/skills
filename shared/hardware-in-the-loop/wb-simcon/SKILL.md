---
name: wb-simcon
description: 什么时候用我：要让模拟集中器（simcon）在 CCO 本地总线上发一帧并判定对端反应——跑一遍多步验证任务（verify）、单步下发 afn/fn（step）、只等一帧 CCO 主动上报（recv_only）、下发前先语义构帧预览（build）、按 run_id/会话翻收发帧日志（frames）、查 06H 上报与查询快照库（store）、跑并发抄表/档案/在网/recipe。碰到"构帧失败:缺少参数 X"、verify 卡住、并发 verify 409、等帧超时原因看不明白时也用我。模拟电表（simeter）不归我。
argument-hint: "[任务，例如 跑一遍 anhui 验证任务 / 只等 06H-F230 上报 30 秒 / 预检 10H-F230 构帧 / 查本次运行发了哪些帧]"
metadata:
  author: reasonix
  version: "1.0.0"
  applies-to: 任意工作区（<WORKBENCH_ROOT> 路径根解析见 /root/.dsh/skills/wb-base/SKILL.md）
  source: 拆自 ai-control-plane（2026-10-28）
---

# 模拟集中器：验证任务 / 单步下发 / 帧日志（wb-simcon）

本技能只讲**模拟集中器**这一条路：`/api/ai/v1/simcon/*`（带 token 的 AI 面）与
`/api/simcon/*`（直连面，无 Bearer）、必需参数、会话/run_id 取帧、并发准入与证据纪律。
归别的子技能的事：开串口前的桥 preflight 与映射判读 → `/root/.dsh/skills/wb-serial/SKILL.md`；
模拟电表 sim_meter（645 从站）→ `/root/.dsh/skills/wb-simeter/SKILL.md`；
离线构帧/回验（不碰串口）→ `/root/.dsh/skills/wb-appframe/SKILL.md`；
侦听台取证与组网诊断 → `/root/.dsh/skills/wb-listener/SKILL.md`；
授权签发、token/scope、v2 任务门面 → `/root/.dsh/skills/wb-base/SKILL.md`。

## 0. 三类动作怎么选（先选动作，再核参数）

| 你要的结论 | 动作 | 端点 | 同步性 | 失败时你先看什么 |
| --- | --- | --- | --- | --- |
| 一组步骤整体过不过（回归/验收） | 运行验证任务 | `POST /api/ai/v1/simcon/verify` | 异步 **202** + `operation_id`，**不可取消** | `result.steps[].pass/fail` + `summary.verdict` |
| 一发一收是否符合预期（调单点） | 单步下发 | `POST /api/ai/v1/simcon/step`（带 `send`） | 同步 | `step.pairing`/`step.deny`/`step.bystanders[]` |
| CCO 会不会自己上报（等事件） | 只等一帧 | `POST /api/ai/v1/simcon/step`（`recv_only:true`+`expect`） | 同步（受 `expect_timeout` 约束） | 超时原因里的逐帧差异（如 `AFN 不匹配: 期望0x0A, 实际0x10`） |
| 这帧到底长什么样（下发前预检） | 语义构帧预览 | `POST /api/simcon/build` | 同步、**不触串口**、无 Bearer | 422 的缺参/非法字段提示 |
| 刚才那批到底发了什么 | 取帧日志 | `GET /api/ai/v1/simcon/frames` | 同步只读 | `entries[]` 的 `frame_hex`/`parsed` |

选完动作再核 §2 的必需参数表：**参数不全会以 422 死在构帧阶段**，别把它当成链路问题。

> 来源：references/simcon.md:1-2,14-27,28-46；references/api-contract.md:195-222；references/operation-guide.md:344-349

## 1. 前置（每次开 simcon 之前）

> **红线 · 必须显式给口（红线级要求，不是建议）**：任何 `verify` / `step` 的 `task`——包括 v2 `verification-runs` 的
> `task`，以及先 `build` 预检再下发的那一整条链——**必须显式给 `mapping_id`**（`simcon` / `cco-main` /
> `sta-main`），**绝不依赖自动选口**。实测不传口时它自选了 `/dev/ttyS0`，报
> `Could not configure port: (5, 'Input/output error')`，还在 `data/logs/simcon/` 留下
> `sc-20261028-114010--dev-ttyS0.jsonl`；显式 `"mapping_id":"simcon"` 后立刻成功
> （`port=/run/hplc/serial/simcon`，115200/N）。自动选口会掉到裸 tty，违反本项目串口红线。

> **前置（每次开 simcon 之前）**：先跑 `/api/serial-bridge/status` + `/verify`，确认**目标口**
> `workbench_ready=true`（别的口离线不算失败）。`simcon` 口实测 **115200/E/8/1**（映射 baud 115200，
> 2026-10-28）；**baud 以 `/api/serial-bridge/status` 的 `mapping.baudrate` 为准，勿记档位**。
> CCO 复位用本地 `01H-F1`；14-F2 匹配 `fn:2`（不是 242）。细节见 `references/serial-bridge.md`。

> resource 固定 `simcon`；所有收发的 1376.2 帧都会进**会话帧日志**并持久化到
> `data/logs/simcon/sc-*.jsonl`。

> 来源：references/simcon.md:3-12；references/operation-guide.md:346-348；references/serial-bridge.md:104
> 来源：validation-20261028/F2（T3 实机：不传口→`/dev/ttyS0` EIO；显式 `mapping_id:"simcon"`→115200/N 成功）

## 2. 必需参数表（本技能的核心，逐动作核对）

| 动作 | 必需 | 关键可选（有默认值） | 落错的表现 |
| --- | --- | --- | --- |
| `verify` | `steps[]`（非空，逐项含 `send`）、`send.afn`、`send.fn`、`send.params`、**`mapping_id`（红线，不许靠自动选口）** | `profile`（全局信息，见下）、`id`、`client_request_id`、`port`、`fail_fast=true`、`enable_responder=true`、`responders` | 422 参数非法；空 `steps` 不碰串口仍返映射解析 |
| `step`（下发） | `send`（**与 `recv_only` 二选一**）、`send.afn`、`send.fn`、`send.params`、**`mapping_id`（红线）** | `profile`、`expect`、`expect_timeout`、`auto_expect=true`、`expect_no_reply`、`enable_responder`、`name`、`client_request_id`、`port` | 422 参数非法 / 409 口被占 |
| `step`（只等一帧） | `recv_only:true`、`expect.afn`、`expect.fn`、`expect_timeout`（不给就走默认档位，等错目标会白等）、**`mapping_id`（红线）** | `session_id`、`port` | 超时并透出逐帧不匹配差异 |
| `build`（预览） | `afn`、`fn`、`params` | `direction=down`、`profile`、`seq=1` | **422**「构帧失败:缺少参数 …」 |
| `open` | **`mapping_id`（红线）** | `port`、`baudrate`、`bytesize`、`parity`、`stopbits` | 省略 `mapping_id` 会走自动选口（`/dev/ttyS0` → EIO）；409 打开失败 |
| `close` | 无 | — | — |
| `batch_read` | `meters[]`（12 位表地址） | `max_concurrent=5`、`mode=single\|batch`、`protocol_type=2`、`timeout`、`profile`、`port` | 422 / 409 |
| `recipes/{id}/run` | 路径里的 `recipe_id`（先 `GET /recipes`） | `{"overrides":{…}}` | 404 不存在 / 422 参数非法 / 409 执行失败 |
| `archive/query` | 无 | `start=0`、`count=200`、`timeout=5.0` | 409 串口未开 / 504 超时 |
| `frames` | 无 | `run_id`、`session_id`、`direction`、`updown`、`afn`、`fn`、`kind`、`after_seq`、`limit≤500` | 404 无会话 |

### 2.1 `verify.steps[]` 每个 step 的字段

- `send`：**只写 `afn`/`fn` + `params`**（ADR-5 语义化；传 `raw` 直接报错）。
- `name`（步骤名，回报里用它定位）、`expect`、`expect_timeout`、`expect_no_reply`。
- 全局信息（地址、协议类型等）由 `profile` 提供，文件在 `apps/workbench/scenarios/profiles/*.json`；
  换台区/换省就换 profile，别把地址塞进 `params` 冒充。

### 2.2 `params` 里的键随 afn/fn 而定（昨夜那个 `duration` 就出在这）

`params` 是**语义参数字典**，键集合由 afn/fn 的构帧契约决定；少一个就 422，措辞是
「构帧失败:缺少参数 <名字>」。**下发前先用 `build` 预览**（只经 scenario_codec 算字节、不触串口），
缺参在这一步暴露，代价是 0 秒、0 帧、0 串口；等进了 `verify`/`step` 才发现，就要多排查一轮链路。

### 2.3 AFN/Fn 记法（写错现在会被**当场 422 拒绝**）

- **`afn` / `fn` 一律不带 `H`**。`10H-F1` 是《协议库》里的口语记法，**不能直接填进 API**。
- 合法写法：
  - `afn`：两位十六进制字符串 `"10"`（= 0x10，按字节取值，不是十进制）、`"0A"`，或整数 0~255
  - `fn`：`"F1"` / `"F230"`（十进制语义，`"F230"` = 230）或整数 0~255
- **写错不会再伪装成"设备没响应"**（2026-10-28 `8276bc8` 修复）：提交即返回
  `422 steps[0].send.afn 格式非法："10H"。合法写法：两位十六进制、不带后缀（如 "10"），或整数 0-255`，
  **且不会创建 job**。旧版是 202 建 job → 后台构帧失败 → `result=fail`、`sent_hex=""`，与"设备不应答"无法区分。
- 整数越界（如 `afn=300`）现在也是 422，不再静默 `&0xFF` 截断。
- 注意 `expect.afn/fn` 目前**不做格式校验**（只参与匹配）：写成 `"10H"` 不会 422，只会匹配不上 → 表现为超时失败。

### 2.4 `pass` 有两种含义，别混

| 步骤里有 `expect` 吗 | result | 关键字段 | 能证明什么 |
| --- | --- | --- | --- |
| 没有 | pass | `reason="仅下发，无接收断言"`、`matched=null` | 只证明**帧发出去了** |
| 有 | pass | `reason="匹配成功"`、`matched="<对端实际回的帧 hex>"` | 才证明**对端应答了** |

判「对端有没有反应」**必须带 `expect`**；别拿"仅下发"的 pass 当成功（2026-10-28 实测 job-9da077347b8a4749 / op-8f81c527a9a64fe4）。

> 来源：references/simcon.md:20-25,31-46；references/api-contract.md:205-213；references/operation-guide.md:350-390,425-428

## 3. 跑验证任务（异步，不可取消）

**先分叉**：**无 token**（本机 `local_full` 免 token，AI 不自签授权）→ v2 `verification-runs`；
**有 token**（人已签发）→ v1 `simcon/verify`。两条路跑的是同一套 simcon 验证，只是门面不同。

```bash
# 无 token：v2。body = 把 v1 verify 的整体包进 "task"，task 里必须带 mapping_id
curl -X POST http://127.0.0.1:8790/api/ai/v2/verification-runs -H "Content-Type: application/json" \
  -d '{"task":{"mapping_id":"simcon","profile":"anhui",
        "steps":[{"name":"s1","send":{"afn":"10","fn":"F1","params":{}}}],
        "client_request_id":"v-001"},
      "client_request_id":"vr-001"}'
# → 202 + job_id → GET /api/ai/v2/jobs/{job_id}?wait_seconds=30
```

- **v2 的 body 形状是硬要求**：`{"task":{…v1 verify 的 body…}}`。把 v1 平铺字段写在上层
  （顶层 `id`/`profile`/`steps`）直接 **422 `Extra inputs are not permitted: id/profile/steps`**——
  **v1 平铺写法的字段一个都不能带上来，连 `id` 也不行**。`task.mapping_id` 必给（§1 红线）。
- v2 job 的 `succeeded` 只代表跑完，业务结论看 `summary`（形如
  `verification_run succeeded: pass (1 pass/0 fail)`）；失败时 L1/L2 可能是空的，看
  `<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json` 里该 op 的 `error`
  （口径见 `/root/.dsh/skills/wb-base/SKILL.md` §3.4）。

```bash
# 有 token：v1 专家面（同一套验证）
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/verify \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"id":"t1","profile":"anhui",
       "steps":[{"name":"s1","send":{"afn":"00","fn":1,"params":{}}}],
       "mapping_id":"simcon","client_request_id":"v-001"}'
```

- 202 + operation_id → `GET /operations/<id>/wait` 到 succeeded；
  `result` 含 steps/summary/`run_id`/`frames_seq`（本次运行的帧 seq 区间）。
- `send` 只写 `afn/fn + params`（ADR-5，传 `raw` 报错）；profile 在
  `apps/workbench/scenarios/profiles/`。
- 并发 verify 返回 409。
- 同一会话同一时刻只允许一个验证任务（并发 `409`）；任务**不可取消**（同烧录），
  提交后耐心等到终态，不并发重试。
- 想直接驱动一次全链路拿报告、不要授权审计时，还有编排面 `POST /api/run`（无 token，
  轮询 `GET /api/run/<id>`、报告 `/<id>/report`、产物 `/<id>/artifacts`、取消 `POST /<id>/cancel`）；
  要授权审计/证据链/幂等则走本节 v1 路径。

> 来源：references/simcon.md:14-27；references/operation-guide.md:350-365,467-480；references/api-contract.md:205,379-391
> 来源：validation-20261028/F3（T3 实机：平铺 v1 body → 422 `Extra inputs are not permitted: id/profile/steps`；包 `task` 后 202）

## 4. 单步下发 / 只等一帧（同步）

```bash
# 下发指定 afn/fn（task 里点名 mapping_id，别靠自动选口）
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/step \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"send":{"afn":"10","fn":"F230","params":{}},"mapping_id":"simcon","profile":"anhui","client_request_id":"s-001"}'

# 只等一帧：感知 CCO 主动上报（30 秒内等到 06H-F230 上行即成功）
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/step \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"recv_only":true,"expect":{"afn":"06","fn":"F230"},"expect_timeout":30,"mapping_id":"simcon"}'
```

- `send` 与 `recv_only` **二选一**；`expect` / `expect_no_reply` 语义与验证任务 step 一致。
- `expect_timeout` 不传（`null`）时按 `expect_rules` 的 per-Fn 档位自动取值
  （默认 5s / 单抄 59s / 并抄 99s）；想卡住某一类帧就显式给秒数。
- `auto_expect=true` 且未显式给 `expect` 时按规则库自动生成预期，结果附
  `step.pairing{rule_id,desc,expect,form,timeout}`；否认帧附 `step.deny{code,code_hex,text}`；
  插播帧附 `step.bystanders[]`。
- 超时原因会带逐帧差异（如 `AFN 不匹配: 期望0x0A, 实际0x10`），据此自纠记法或目标。
- 支持 `client_request_id` 幂等（重复提交复用原操作，内容不一致 `409`）。
- 应答规则可查：`GET /api/simcon/expect_rules`（`deny_codes`、`timeout_tiers`、`no_expect_afn`）
  与 `GET /api/simcon/responders`（内置+覆盖）。

> 来源：references/simcon.md:28-46；references/api-contract.md:206-212；references/operation-guide.md:366-390

## 5. 会话与 run_id 取帧日志

```bash
# 本次运行下发过什么帧（run_id 来自 verify/step 响应）
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?run_id=<run_id>&direction=tx" \
  -H "Authorization: Bearer <token>"

# CCO 主动上报过什么帧（updown=up 即上行帧）
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?updown=up" \
  -H "Authorization: Bearer <token>"

# 有没有某类 afn 的上行帧
curl "http://127.0.0.1:8790/api/ai/v1/simcon/frames?updown=up&afn=06" \
  -H "Authorization: Bearer <token>"
```

- 过滤：`direction`(tx/rx)、`updown`(up/down)、`afn`、`fn`、
  `kind`(step_send/manual_send/auto_reply)、`run_id`、`session_id`、
  `after_seq`+`limit`(≤500) 游标翻页；每帧含 `frame_hex`/`parsed` 解析结果。
- **响应信封 `{session_id, entries[], next_after_seq, matched_total, has_more, counts{tx,rx,uplink}}`**
  —— 帧列表在 `entries` 键（不是 `frames`），翻页传 `after_seq=next_after_seq`。
- 定位顺序：`run_id`（这一次运行）→ `session_id`（这一路会话）→ 全量 + `updown/afn` 过滤（找上行）。
- **持久化库对照**（`data/listener_13762.sqlite`，只读 GET、库未启用 503、信封 `{"items":[…]}`）：

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

- 区别：`/simcon/frames` 是**本次会话**的帧序列（`sc-*.jsonl`，实时）；store 是**持久化库**，
  跨会话保留（按天滚动 5 天）。查"刚才那批"用 frames，查"前天那批上报落库没有"用 store。

> 来源：references/simcon.md:47-62,69-91；references/operation-guide.md:391-410；references/api-contract.md:214-218

## 6. 会话管理

```bash
curl http://127.0.0.1:8790/api/ai/v1/simcon/session -H "Authorization: Bearer <token>"
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/open \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"mapping_id":"simcon"}'
curl -X POST http://127.0.0.1:8790/api/ai/v1/simcon/close \
  -H "Authorization: Bearer <token>"
```

- `GET /api/ai/v1/simcon/session`：当前/最近会话信息。
- `POST /api/ai/v1/simcon/open`（body 给 `{"mapping_id":"simcon"}`；**省略会走自动选口**，掉到裸 tty 报 EIO）、`POST /api/ai/v1/simcon/close`：
  显式管理；close 释放串口，日志保留可查。
- 单步下发会自动开会话；用完即 `close`，别把口长时间占着。

> 来源：references/simcon.md:63-68；references/operation-guide.md:411-421；references/api-contract.md:196-201,218

## 7. 语义构帧预览与内置应答（无鉴权辅助端点）

```bash
# 语义化构帧：只经 scenario_codec 算字节，不触串口——下发前预检报文用
curl -X POST http://127.0.0.1:8790/api/simcon/build -H "Content-Type: application/json" \
  -d '{"afn":"10","fn":"F230","params":{},"direction":"down","profile":"anhui","seq":1}'
# → 200 {"hex":"68 ...","length":N}；构帧失败 422

# 当前生效应答规则（内置+覆盖）
curl http://127.0.0.1:8790/api/simcon/responders
```

这两个端点在 simcon 命名空间（`/api/simcon/*`），**不经 /api/ai/v1、无 Bearer 鉴权**；
`build` 是 §2.2 的下发前编译步骤，`GET /status`（`{open, port, mapping_error, pending_frames, session}`）
与 `GET /ports` 也在这层，可先看口开没开。

> 来源：references/simcon.md:92-96；references/operation-guide.md:422-435；references/api-contract.md:196-201,213

## 8. 并发与准入（谁在占口 → 为什么 409）

- **事实**：simcon 口是**物理独占**——同一物理口同一时刻只有一个持有者，被占用返回 `409`，
  这不是故障（AI 与前端、两名执行者同规则）。可提交的并发证据：`verify` 并发提交即 `409`
  （同一会话同一时刻只允许一个验证任务，且不可取消）；`step`/`open`/`batch_read` 同样因口被占返 `409`。
- **统一闸门已上线（2026-10-28 `90eead7`）**：`verify` / `step` / `open` / `close` **四个入口共用一把闸门**，
  同一时刻只允许一个在跑。旧版只有 `verify` 有闸，`step`/`open`/`close` 能在 verify 跑着时插进来——
  最严重后果不是失败而是**假通过**：verify 等应答时被别人的 `step` 帧喂到，把别人的应答当成自己的、
  判 `pass` 写进结果表，事后无人能发现。`close` 更狠，会把串口从进行中的 verify 底下抽走。
- **409 现在会告诉你谁在用**（实测原文）：
  `已有模拟集中器任务在运行：actor=local:loopback，动作=verify，已运行 1.4s，operation=op-824182f2c7534422`
- **随时可查占用（只读，不阻塞）**：
  ```bash
  curl -s http://127.0.0.1:8790/api/ai/v2/simcon/lease
  # 空闲:   {"held":false,"holder":null,"policy":"no_queue_reject"}
  # 占用中: {"held":true,"holder":{"actor":"local:loopback","kind":"verify",
  #          "operation_id":"op-…","started_at":"2026-10-28T…","elapsed_seconds":0.74,
  #          "thread":"ai-simcon-verify"},"policy":"no_queue_reject"}
  ```
  提交前先查它：`held=true` 就别提，按 `elapsed_seconds` 估还要等多久，不要盲重试。
- **策略是"拒绝"不是"排队"**（`policy=no_queue_reject`）：没有人替你排队，被拒就等或改时段。
- **两条已知边界**：① 闸门只覆盖 **AI 面**；GUI 页面与串口 Profile 应用走 `/api/simcon/*` 直连面，
  仍可绕过——所以"人点页面"与"AI 跑 verify"同时进行时，仍可能混流；② `step`/`open`/`close` 走 **v1**
  （需要 Bearer token，`local_full` 免 token 只对 v2 生效），而闸门对 v1/v2 一视同仁。
- **产物目录按批分开**：每批验证单独一段 `run_id` 与独立会话文件
  `data/logs/simcon/sc-<时间戳>-<端口>.jsonl`；取证据只认**本批 run_id + 本会话 session_id**。
- **同批两份证据一律作废**：两名执行者同时抢同一口会**帧混流、产物互覆写**，此后同一批的
  两份"证据"都无法归因——发现混流就作废本批、重新独占跑一遍，不要挑一份像样的交差。
- 跨批对比时先对齐 `profile` 与 `expect_rules` 版本，否则判定口径不同，比出来的是假差异。

> 来源：references/operation-guide.md:346-349,363-365；references/api-contract.md:51-62,195-222；references/simcon.md:9-12,26；references/serial-bridge.md:104；REQS.md:31（P1-1 需求口径，未实现）

## 9. 红线

1. **不可取消的不重试**：`verify` 与烧录一样提交即跑完；卡住就等 `wait` 到终态，不并发重提。
2. **409 不抢口**：等对方 `close` 或改 `port`，不反复重试、不偷偷 `open` 抢。
3. **口必须点名（红线级）**：`verify`/`step`/`open` 一律显式给 `mapping_id`，**绝不依赖自动选口**——不传会掉到 `/dev/ttyS0` 报 `Input/output error`，还留下 `sc-*-dev-ttyS0.jsonl` 脏批（§1）。
4. **`raw` 别塞**：`send` 只接受 `afn/fn + params`（ADR-5），要塞字节去 `wb-appframe` 的离线构帧。
5. **先 build 再 step/verify**：参数不全的花费在 `build`（0 帧）而不是在链路上（多轮排查）。
6. **只读取帧**：`frames`/`store/*`/`session` 都是只读；不写库、不改 `sc-*.jsonl`、不动 profile 文件。
7. **不复用别人的批次**：只交本批 `run_id` 的证据；混流批次按 §8 作废重跑。

## 10. 参考

- 源文件（老门面，只读）：`references/simcon.md`、`references/api-contract.md`（§1.1/§1.2/§5）、
  `references/operation-guide.md`（§9.1-§9.5）、`references/serial-bridge.md`（preflight 与映射表）。
- 直连面无 token 的一组（并发抄表/档案/recipes/统计，契约见 `references/api-contract.md` §5）：
  `POST /api/simcon/batch_read`（`meters[]`、`max_concurrent=5`、`mode=single|batch`、`protocol_type=2`）、
  `GET /api/simcon/batch_read/{job_id}`、`POST /api/simcon/batch_read/{job_id}/stop`、
  `GET /api/simcon/recipes`、`POST /api/simcon/recipes/add_archive/run`、
  `GET /api/simcon/archive/query?start=0&count=200`、`GET /api/simcon/online`、
  `GET /api/simcon/report_buckets`、`GET /api/simcon/batch/stats?period=15m`；
  job 快照结构 `{job_id, meters_total, max_concurrent, in_flight, queued, done, success, failed, deny_breakdown, finished, rows[]}`。
- 配置事实源（相对 `<WORKBENCH_ROOT>`）：`apps/workbench/scenarios/profiles/*.json`、
  `serial_ports.json` 映射；应答规则库经 `GET /api/simcon/expect_rules` 现取，勿凭记忆写死档位。

> 来源：references/simcon.md:92-119；references/api-contract.md:195-222；references/operation-guide.md:344-435


---

## 附录 · 深水事实库（事实来源，按节读，不复制）

本技能只讲**怎么做**。精确字段、全部端点、全流程手册在入口技能的事实库里，**只有本文答不清或要核对字段时才翻对应小节**，不要整份读：

| 文件 | 该读哪一节 | 行数 |
|---|---|---|
| /root/.dsh/skills/ai-control-plane/references/simcon.md | 验证任务/单步/帧日志/并发抄表/档案全表 | 120 |
| /root/.dsh/skills/ai-control-plane/references/api-contract.md | §5 simcon 契约 | 491 |
| /root/.dsh/skills/ai-control-plane/references/operation-guide.md | §9.1-9.5 原始操作步骤与示例 | 520 |

- 旧门面归档（v2.9 路由表、实测校准段、REQS 编号索引）：/root/.dsh/skills/ai-control-plane/references/_归档-门面v2.9.md（257 行，**仅当新文档查不到时**参考）

> 铁律：事实库里改动只改一处；子技能里**不复制**事实库内容，避免两份说法打架。
