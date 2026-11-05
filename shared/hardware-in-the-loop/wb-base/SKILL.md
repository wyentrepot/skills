---
name: wb-base
description: 共享基座子技能：工作台在线任务的接入与授权（路径根解析、部署形态与前缀映射、平台端点、启动配置、grant/scope/resource/token）、v2 任务门面（能力清单与源健康、四步任务流、job 与证据读取、v1 专家兼容）、证据口径（L1/L2/L3、观察任务语义、证据落盘）、契约红线与错误码速查。任何在线任务开始前读本技能。
argument-hint: "[任务，如 拿 token / 看 capabilities / 读 job 证据 / 查错误码]"
metadata:
  author: reasonix
  version: "1.0.0"
  applies-to: 任意工作区（<WORKBENCH_ROOT> 按序单点解析见 §1.1）
  source: 拆自 ai-control-plane（2026-10-28）
---

# wb-base · 接入·授权·证据·错误码

## §0 本技能只讲什么 / 别的事去哪

只回答四类问题：**怎么连上工作台**（端口/前缀/路径根/启动）、**凭什么权限调**（grant/scope/resource/token）、**什么算证据**（L1/L2/L3 口径、观察语义、落盘）、**出错怎么自纠**（错误码与红线）。

先判一次在线还是离线，判完直接走对应子技能，不重复判：**离线**（只有帧/日志/文件）→ 帧解析/构帧/回验进 `wb-appframe`，分钟采集漏点/11E4/11E3/时钟偏移走 `mclt-collect-analysis`；**在线** → 读本技能拿接入与授权，再只读那一个 wb-* 子技能，用完即止；**拿不准后端有什么** → 先让工作台报一次能力清单与源健康（§3.1），再回到在线判定。

| 我要干什么 | 读哪节 / 哪个技能 |
| --- | --- |
| 不知道 `<WORKBENCH_ROOT>` 在哪、路径对不上 | 本技能 §1.1 |
| 分不清 8790/8765/8766/8781、前缀被剥还是透传 | 本技能 §1（前言） |
| 工作台起不来、起了但 v2 要 token、要停进程 | 本技能 §1.3 |
| 要一份 token、要最小 scope、要撤销授权 | 本技能 §2 |
| 先看后端有哪些能力/源是否健康再选路 | 本技能 §3.1 |
| 提交任务、等 job、按需取 L1/L2/L3 证据 | 本技能 §3.3—§3.5、§4 |
| 旧客户端/专家诊断要细粒度端点 | 本技能 §3.7 |
| 判"这条结论算不算证据""为什么是 inconclusive" | 本技能 §4 |
| 只想跑一次全链路验证拿报告（无 token） | 本技能 §5.1 |
| 401/403/404/409/422/503 怎么处置 | 本技能 §7 |
| 烧录固件并判定是否真烧成 | `wb-flash` |
| 侦听台建索引、查已解析帧、通信流追踪、组网诊断 | `wb-listener` |
| 模拟电表 645 从站调测 | `wb-simeter` |
| 模拟集中器验证/单步/并发抄表/档案 | `wb-simcon` |
| 开串口前的 serial-bridge preflight、模块串口会话 | `wb-serial` |

> 来源：ai-control-plane/SKILL.md

## §1 接入

### 前言：部署形态与前缀映射（最容易踩的一层）

- **入口**：统一工作台 `apps/workbench/run.py` → **8790**，`/api/*` 各命名空间，页面 `/static/pages/<页名>/`、外壳 `/`；侦听台独立版 `apps/listener/run.py` → 8765，`/api/*`（无业务段）；模块日志独立版 `apps/module_log/run.py` → 8766，`/api/module-serial/*`；simcon 独立版 `python -m sim_concentrator.api` → 8781，`/api/simcon/*`。
- **挂载代理语义**：**外部路径 = `{api_prefix}{rest}` → 子应用收到 `{sub_root}{rest}`**。`/api/listener/*` 由 listener 接、**剥业务段**（`/api/listener/logs/status` → 子应用 `/api/logs/status`）；`/api/module-serial/*`、`/api/fs/*`、`/api/loghooks/*` 由 module_log 接、同前缀透传；`/api/simcon/*` 是 simcon **平级顶层 mount**（REQS-0023，不经 module_log，无剥前缀）；`/api/ai/v1/*` 与其余 `/api/*` 由 workbench 自身接（AI 控制面 / 编排·字典·串口 Profile）；`/static/*`、`/` 走静态外壳（NoCacheHTMLStaticFiles）。
- **双前缀特例（勿"修正"）**：listener 子应用自身有 `/api/listener/*` 路由（traces、indexes），叠加挂载前缀后外部路径是 **`/api/listener/listener/traces`**（trace.js 就这么调）。indexes 同时暴露为 `/api/indexes` 与 `/api/listener/indexes`，故外部两种写法都有效。
- **挂载降级**：listener 依赖 C# DLL/pythonnet，挂载失败自动降级（`GET /api/platform-version` 里 `listener_mounted=false`，页签显示"不可用"），不拖垮整体。
- **平台端点**：`GET /`（外壳）、`GET /api/platform-version`（`{app, version, module_log_mounted, listener_mounted}`）、`GET /api/health`（`{status:"ok", app:"workbench"}`，免鉴权探活）、`POST /api/shutdown`（uvicorn graceful 停机，进程退出）。

> 来源：ai-control-plane/references/api-contract.md

### §1.1 路径根解析（`<WORKBENCH_ROOT>` 按序单点解析）

技能自带的 `references/`、`scripts/`、`使用经验/` **相对本技能目录**，直接存在，无外部依赖。仓库内路径（`apps/`、`docs/`、`tools/`、`data/`、`.build_plain/`、`DECISIONS.md`）**一律相对 `<WORKBENCH_ROOT>`，不写死绝对路径**，按序解析、命中即停：

1. 环境变量 `WORKBENCH_ROOT`；
2. 配置文件 `~/.config/workbench/repo-root`（一行绝对路径，仓库搬家只改这一处）；
3. 从当前目录向上探测 `apps/workbench` 目录标记（工作区本身就在仓库内时免配置）。

解析不到就**先向用户确认**，不要凭记忆猜路径、不要猜 COM 号。库存校验脚本用同一顺序（`--repo-root` 显式参数最优先），找不到时给明确报错；它只构造惰性 stub，**不开串口、不启动侦听台、不执行烧录**：

```bash
python tools/scripts/verify_api_inventory.py [--json] [--repo-root <WORKBENCH_ROOT>]   # 仓库内工具
```

`使用经验/` 的定位（维护边界）：只放**跨环境的一次性事实与过程复盘**；能固化为边界条款的内容（启动姿势、红线、路由判定、数据源清单）一律写进 SKILL.md / references 正文，不再追加条例，防止双份文档漂移。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/features.md

### §1.2 启动与配置

```bash
# 任意 cwd 可启动（run.py 自动把仓库根/apps/libs 注入 sys.path，不依赖 cd/PYTHONPATH）
python3 <WORKBENCH_ROOT>/apps/workbench/run.py

# 桌面 / WSL 人机环境可后台常驻（沙箱禁用，见下）
WORKBENCH_LOCAL_FULL_ACCESS=1 HPLC_OPEN_WORKBENCH=0 \
  nohup python3 <WORKBENCH_ROOT>/apps/workbench/run.py > /tmp/wb.log 2>&1 &
```

- **`WORKBENCH_LOCAL_FULL_ACCESS=1` 必须带**：漏掉则 `GET /api/ai/v2/capabilities` 直接 401「缺少 Bearer token」，AI 会误以为要找人要 token 而绕路。`HPLC_OPEN_WORKBENCH=0` 供 headless/无图形环境关掉自动开浏览器。
- **后台常驻按环境二选一**：agent 沙箱/容器（子进程随外层 shell 结束被回收）**必须用受管后台任务**，日志从该任务输出读，**不要用 nohup**；桌面/WSL 才可用 nohup。
- **停止**：禁用 `pkill -f "workbench.run"`（会命中执行该命令的 shell 自身导致自杀）。先 `pgrep -af "[w]orkbench.run"` 取 PID 再 kill，或直接终止受管后台任务。
- **人工授权密钥**（仅"AI 自动拿授权"需要）：启动前设 `WORKBENCH_AI_ADMIN_KEY`，或用 `tools/scripts/一键生成AI密钥.bat` 一键装好；未配置时 admin 授权接口返回 `503 未配置人工授权管理密钥`。日常人工点页面不需要它。
- **一键启动包**用 `git archive HEAD` 打包：**未提交的改动不生效**（改页面/后端先提交再打包）。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md

## §2 授权：grant / scope / resource / token

### §2.1 边界与签发（人执行）

授权**只由人签发**：仅限 workbench 本机 `127.0.0.1` + `X-Workbench-Admin-Key` 请求头；AI 只使用人已签发的 token，**不自签、不扩权、不转交**。前置是工作台已在 8790 运行（`curl http://127.0.0.1:8790/api/health` → 200）且已配置 admin key。

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/admin/grants \
  -H "X-Workbench-Admin-Key: <WORKBENCH_AI_ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"scopes":["observation:create","evidence:read"],"resources":["*"],"ttl_seconds":3600,"reason":"监控cco日志"}'
# → {"grant":{"grant_id":"grant-...","scopes":[...],"resources":[...],"expires_at":"...","firmware_roots":[...]},"token":"xxxx"}
```

- **scope 最小化**：只申请本次任务需要的（§2.2），上面的例子就是"只监控日志"的最小集。`resources` 取 `*` 或具体 `mapping_id`/`session_id`；`ttl_seconds` 1–86400；`max_operation_seconds` 可选（默认 1800）。
- **要烧录必须给 `firmware_roots`**（允许的固件目录白名单数组），否则（v1 / 局域网面）flash 返回 **403「当前授权未配置允许烧录目录」**。
- **白名单两来源（2026-10-28 `d5719b7` 起 v1/v2 统一）**：`grant.firmware_roots` 优先 → 回退环境变量 `WORKBENCH_AI_FIRMWARE_ROOTS` → 都空则 403。`local_full`（本机 loopback 免 token）下没有 grant，白名单由 env 顶上；**没配 env 就 403**。放行时写 `store.audit(action="flash.authorization")`，记 `authorization_source`（grant/env/local_full_env）+ `bin_path` + 命中的 root。**团队红线：烧录必须由人授权**，不得靠 env 给自己开白名单。
- `token` **只返回一次**（服务端只存 SHA-256 摘要）——务必当场保存，AI 全程只用 token。`503` = admin key 未配置/没重启；`403` = key 错或非本机发起。

> 来源：ai-control-plane/references/auth.md；ai-control-plane/references/operation-guide.md
> 来源：validation-20261028/F5（T4 实机：v2 `local_full` 零授权、无 `firmware_roots` 也烧成 STA）

### §2.2 scope → 能力映射（14 种）

| scope | 能力 | 所需资源 / 典型任务 |
| --- | --- | --- |
| `status:read` | `/status`、`/audit` | `*` 或资源；探状态、看审计流水 |
| `module_session:ensure` / `:stop` | 确保/创建、停止模块串口会话 | mapping_id / 会话 |
| `module_send:execute` | 向模块会话发送指令 | 会话 |
| `module_flash:execute` | 烧录固件 | 会话（另需 `firmware_roots`） |
| `listener:ensure` / `listener:stop` | 侦听台采集开 / 停 | mapping_id；停止时在线用当前 mapping_id、离线回退 `listener-main` |
| `listener:trace` | 创建通信流追踪（回放/live） | 当前侦听台 mapping_id / `listener-main` |
| `observation:create` | 建观察任务、取消操作 | mapping_id / 会话；监控日志、盯帧 |
| `evidence:read` | 读 operation / Artifact / 帧索引/追踪 | 对应资源；取证、查帧（监控行也必需） |
| `simcon:verify` / `simcon:send` / `simcon:read` | 验证任务 / 单步·开关串口 / 帧日志与持久层读 | `simcon` |
| `simeter:read` | 模拟电表状态/帧日志只读（v2 `simeter_frames.read`） | 模拟电表观察；写操作免 token 直连 `/api/simeter/*` |

**资源（resource）**：串口类用 `serial_ports.json` 的 `mapping_id`：`cco-main`、`sta-main`、`listener`（实际 COM 号随接线变化，**调用方优先用 mapping_id，不硬编码 COM 号**）；simcon 口的 task **必须显式 `mapping_id:"simcon"`**（不传会自选 `/dev/ttyS0` 报 `Input/output error`，见 `wb-simcon` §1；该口实测 115200，baud 以 status 的 `mapping.baudrate` 为准）；会话资源用 `session_id`（`ms-xxxx`），AI 接口内部归一到其 `mapping_id`。`resources:["*"]` 全放行（谨慎）；越权 403，token 无效/过期/撤销 401。

> 来源：ai-control-plane/references/auth.md；ai-control-plane/references/operation-guide.md；ai-control-plane/references/simeter.md；ai-control-plane/references/auth.md

### §2.3 token 用法与两条访问通道

- 请求头固定 `Authorization: Bearer <token>`；**不要把 token 写进输出、日志、提交内容或证据正文**。
- **v2（默认低 token 面）**：仅在**真实对端为 loopback**（`127.0.0.1`/`::1`）且显式设置 `WORKBENCH_LOCAL_FULL_ACCESS=1` 时进入 `local_full`、免 token，但仍写审计；局域网请求必须 Bearer grant，并按 capability、scope、逻辑资源 alias 过滤。
- **v1（专家兼容面）**：所有业务接口都要 Bearer token——**即使 `local_full` 也一样**（如 `GET /api/ai/v1/listener/indexes`）。admin grant 签发/撤销永远要本机 + admin key。
- **管理辅助**：`GET /api/ai/v1/admin/grants`（列，admin key）、`POST /api/ai/v1/admin/grants/{grant_id}/revoke`（撤销，404）、`GET /api/ai/v1/audit`（审计流水，token + `status:read`，按授权 resources 过滤）。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/auth.md；ai-control-plane/references/operation-guide.md

## §3 任务门面 v2（默认 AI 调用面）

v2 把"查状态、并行观察、模块动作、验证、烧录、取证"收敛为任务级工作流：AI 客户端默认只需要**发现能力、提交一个任务、读取 job、按需取证**四类调用。v1 路由保留给专家诊断和兼容场景，**不因 v2 上线而删除或改名**。

### §3.1 让工作台报一次能力清单与源健康

```bash
curl -s http://127.0.0.1:8790/api/ai/v2/capabilities | python3 -m json.tool
```

一次调用同时拿到 **capability 清单**、**后端健康（`source_health`）**、**逻辑资源 alias**；它**不泄漏 token、物理串口号或绝对路径**——所以别在这里找 COM 号，按 alias 走。

| 响应 | 判读 | 下一步 |
| --- | --- | --- |
| 200 | 能力与源健康已拿到 | 按 `source_health` 挑可用源，按 capability 选任务路径；只走列出的能力 |
| 401「缺少 Bearer token」 | 启动漏了 `WORKBENCH_LOCAL_FULL_ACCESS=1`，或请求不是真 loopback | 按 §1.2 重启；局域网按 §2 拿 token |
| 连接失败/拒绝 | 工作台没起 | 按 §1.2 启动后重试 |
| 部分源不健康 | 该源后端未挂载（如 listener 缺 DLL 降级） | 任务只依赖该源时按 §7 处置；**不要把未挂载源当"没有数据"** |

拿不准后端有什么时，这是**唯一**该先做的调用；判完再进具体子技能，不要凭记忆假设端点存在。

- **已知缺陷 P2-2（尚未修）**：实测该接口返回 11 项能力，但每项 **`id` 为 `null`、`summary` 为空字符串**。**此时不要靠 `id` 选路**——改用 `source_health` ＋ 各子技能里的端点表（条目上可读的还有 `name`/`allowed`/`resources`/`call_examples`）；等 P2-2 修好后再以 `id` 为准。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md
> 来源：validation-20261028/F8（能力 11 项，`id=null`、`summary=""`）

### §3.2 八条公开路径

| 方法 | 路径 | capability | 说明 |
| --- | --- | --- | --- |
| GET | `/api/ai/v2/capabilities` | `capabilities.read` | 能力、后端健康、逻辑资源别名 |
| POST | `/api/ai/v2/investigations` | `investigations.create` | 最多 **3 个** observation 并行编排模块日志、侦听台、simcon |
| POST | `/api/ai/v2/verification-runs` | `verification_runs.create` | 复用既有 simcon 验证；**不是烧录成功的替代** |
| POST | `/api/ai/v2/module-actions` | `module_actions.*` | 显式 `ensure`/`send`/`stop`，禁止任意 action 透传 |
| POST | `/api/ai/v2/flash-jobs` | `flash_jobs.create` | 复用既有烧录控制；固件路径必须在授权 `firmware_roots` 内 |
| GET | `/api/ai/v2/jobs/{job_id}` | `jobs.read` | `wait_seconds=0..30`，GET 无副作用 |
| POST | `/api/ai/v2/jobs/{job_id}/cancel` | `jobs.cancel` | 观察可取消；**烧录/验证拒绝取消** |
| GET | `/api/ai/v2/jobs/{job_id}/evidence` | `jobs.evidence.read` | `level=L1\|L2\|L3`；L1/L2 有界，L3 只返回稳定引用 |

请求/响应都是命名 Pydantic schema；写任务携带 `client_request_id` 实现幂等（重复提交复用原 job）。

**`verification-runs` 的 body 形状（可直接复制）**——v2 只认 `{"task": {…}}`，`task` 里装的是 v1 verify 的整个 body：

```json
{"task": {"mapping_id": "simcon",
          "profile": "anhui",
          "steps": [{"name": "s1", "send": {"afn": "10", "fn": "F1", "params": {}}}],
          "client_request_id": "v-001"},
 "client_request_id": "vr-001"}
```

- 把 v1 平铺字段写在上层（顶层 `id`/`profile`/`steps`）会 **422 `Extra inputs are not permitted: id/profile/steps`**——**v1 平铺写法的字段一个都不能带上来，连 `id` 也不行**。
- `task.mapping_id` 必给（`simcon`/`cco-main`/`sta-main`）；不给会走自动选口、掉到 `/dev/ttyS0` 报 `Input/output error`（见 `wb-simcon` §1）。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md
> 来源：validation-20261028/F3（T3 实机：平铺 → 422；包 `task` → 202）

### §3.3 四步低 token 任务流

1. `GET /capabilities` 发现后端与逻辑资源 alias（§3.1），**不读也不猜物理 COM 号**。
2. 提交一个任务：观察 `POST /investigations`、模块控制 `POST /module-actions`、验证 `POST /verification-runs`（body 形状见 §3.2 的 `{"task":{…}}` 示例）、烧录 `POST /flash-jobs`。
3. `GET /jobs/{job_id}` 读统一状态（可 `wait_seconds` 阻塞）。
4. 只有需要细节时才 `GET /jobs/{job_id}/evidence?level=L1|L2|L3`。

```bash
# 一次并行观察模块日志 + 侦听台历史索引（最多 3 个 observation）
curl -X POST http://127.0.0.1:8790/api/ai/v2/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "case-20260902-001",
    "client_request_id": "case-20260902-001-observe",
    "observations": [
      {"source":"module_log", "target":{"session_id":"ms-xxxx"},
       "window":{"mode":"live","timeout_seconds":120},
       "match":{"kind":"literal","value":"发送成功"}},
      {"source":"listener", "target":{"index_id":"idx-20260902"},
       "window":{"mode":"cursor_range","type":"cursor_range","index_id":"idx-20260902","start_frame_id":1,"end_frame_id":500},
       "match":{"kind":"literal","value":"上行"}}
    ],
    "cleanup":"owned_only"
  }'
```

- 返回 `202` + `job_id`。历史窗口完成后可立即读 job；live 窗口由服务端 worker 推进。
- **`job_state` 是执行状态，`verdict` 只用于 investigation 观察**（`pass/fail/inconclusive/error`）；module_action / verification_run / flash_job 的 `verdict` 恒 `null`，模块动作/验证/烧录成功**不会**伪装成业务 `pass`。
- `cleanup=owned_only` 只清理由本任务创建的资源，不关闭人工或 UI 复用的会话。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md

### §3.3b 找回最近的 job（2026-10-28 新增）

job_id 丢了不用翻 json 文件：

```bash
curl -s "http://127.0.0.1:8790/api/ai/v2/jobs?kind=flash_job,verification_run&state=error&limit=10"
# → {"jobs":[{operation_id,kind,actor,state,created_at,updated_at,client_request_id,error,job_id}],"count":N,"limit":10}
```

- `kind` 可重复（`?kind=flash_job&kind=verification_run`）或逗号分隔；`state` 精确匹配；`since` 为 ISO 时间（非法值 422）；`limit` 默认 20、**硬上限 100**。
- 每条只含元数据（**不含 payload/result**），另带派生 `job_id`，可直接拿去 `GET /jobs/{job_id}` 或 `/evidence`。
- 已知边界：列表**未按资源收敛**——LAN 侧只要有 `jobs.read` 就能看到全部摘要（单条 `read_job` 才逐条校验 resources）。

> 来源：apps/workbench/ai_store.py list_operations、apps/workbench/ai_v2_api.py GET /jobs（2026-10-28 d5719b7 落地，实机验证通过）

### §3.4 提交与读取 job（实测口径）

| 任务 | 最小调用链 |
| --- | --- |
| 发现后端/逻辑资源 | `GET /api/ai/v2/capabilities` |
| 并行观察日志/侦听台/simcon/simeter | `POST /investigations` → `jobs/{id}` → `evidence` |
| 发串口指令（cco/sta） | `POST /module-actions`（action=ensure/send/stop）→ `jobs/{id}` |
| 验证用例/单步 | `POST /verification-runs` → `jobs/{id}` → `evidence` |
| 烧录固件 | `POST /flash-jobs` → `jobs/{id}` |
| 取消 / 读取任务与证据 | `POST /jobs/{id}/cancel`、`GET /jobs/{id}`、`GET /jobs/{id}/evidence?level=L1\|L2\|L3` |

```bash
curl -s "http://127.0.0.1:8790/api/ai/v2/jobs/<job_id>?wait_seconds=30"
```

- **investigation 信封恒为 `queued`**（即使同步历史路径已在返回前执行完）——创建后**必须**读 job 到终态，不能拿 202 响应当结果。
- `GET /jobs/{id}?wait_seconds≤30` 是真阻塞等终态（`0`=立即返回当前快照）；**只轮询快照、无副作用**，不推进任务。
- `verification_run` 终态 summary 带步骤判定（形如 `verification_run succeeded: fail (0 pass/1 fail)`）——**`succeeded` 只代表任务跑完，不代表验证通过**。
- 业务参数在**创建时**校验：非法 `window.mode`、缺 `match`、未知 `session_id`、`minute_periods` 缺 `task_no`、`raw_hex` 无收窄条件，现在直接 `422`（旧行为是 202 后异步 error 且无原因）。
- **异步 error 的原因不在 evidence 里**：实测 `failed` 的 verification job，L1/L2 全是 `items:[]`，只有 `summary:"verification_run error"`。真因在该 op 的 `error` 字段，文件是 **`<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json`**（**不在** `<WORKBENCH_ROOT>/data/...` 下），op id 取 job 信封的 `underlying_refs` / `result.underlying_operation_id`。**证据全空时不要断定"没原因"**，去翻这个文件。
- **读失败原因的顺序（2026-10-28 实测 + 当日修复）**：① `GET /jobs/{job_id}` 看 `result.result.steps[].reason`（构帧/匹配失败的直接原因）；② 同处 `sent_hex`：**为空 = 根本没发出去**，不是「没收到回应」；③ **`GET /jobs/{job_id}/evidence?level=L1`** —— 2026-10-28 `66c8623` 之后**失败任务也会返回证据**（失败步的 `index/name/result/sent_hex/matched/reason`；操作级失败返回一条含 `reason` 的兜底项），不再是空数组；④ `operations.json` 的 `error` 只作最后兜底。
- 注意：`afn` 写成 `"10H"` 这类格式错，自 `8276bc8` 起**提交就 422**、不建 job；若 step 里出现 `构帧失败: ValueError(...)`，说明跑的是旧版，或缺的是别的键（如 `缺少参数 nid`）。

> 来源：ai-control-plane/references/operation-guide.md
> 来源：validation-20261028/F4（T3 实机：`job-b7d16f008543410b` 的 L1/L2 均 `items:[]`，真因在 `op-3d4f9644840c4d6c.error`）

### §3.5 证据三级（L1/L2/L3）与 ref 约定

```bash
curl -s "http://127.0.0.1:8790/api/ai/v2/jobs/<job_id>/evidence?level=L1"
curl -s "http://127.0.0.1:8790/api/ai/v2/jobs/<job_id>/evidence?level=L3&ref=listener:<index_id>:<frame_id>"
```

| 级别 | 内容 | 上限 |
| --- | --- | --- |
| L1 | `index_id`、时间窗、过滤器、总帧数、按帧类型/方向计数、通信流组数、`correlation_status`、解析后端、可下钻 refs；**不含完整帧** | 3 KiB |
| L2 | `index_id`、`frame_id`、`log_time`、`FrmType`、NID、`SRC`、`DST`、`ORI_S`、`ChType`、`APP_ID`、`msg_seq`、`flow_dir`、`meter_addrs`、HEX 命中片段、分钟采集 `freeze_time`/`response_result`、ref | 16 KiB 且 ≤50 条 |
| L3 | 仅对**同一 job** 的 `ref=listener:<index_id>:<frame_id>` 调既有 `get_index_frame`，返回 `raw_hex`、`summary`、`parse_error`、`analysis` 与 trace 链接 | 每次 ≤10 个 ref |

- **ref 格式是 `listener:<index_id>:<frame_id>`**，不是 `index_id:frame_id`；无关 ref 403、格式错 422、单次 >10 个 422。
- 顺序永远是**先 L1 摘要 → 需要时 L2 明细 → 最后 L3 原始帧**，避免把底层原始日志直接灌进上下文。
- **四条铁律**：① `sequence` 是日志采集序号，**不能作为协议关联键**，多中转关联只用同一 `index_id` 内的 `app_id + msg_seq + NID + 时间簇`，无 `msg_seq` 的帧标记 `correlation_status=unavailable`；② 分钟采集业务归属**以 `freeze_time` 为准**，L2 同时给 `log_time` 与 `freeze_time`；③ `parse_backend=none` 时保留索引与原始帧查询、缺字段返回 `parse_unavailable`，**不得把未解析帧归入并发抄表或分钟采集**；④ 三级必须同一历史 `index_id`，跨 index 禁止关联；历史日志保留 `index_id`，实时 `not_seen` 且无可信到达时间只能 `inconclusive`（`live_window_unverified`），**不能据此证明"没有发生"**。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

### §3.6 listener 语义查询（`trace_query` / `minute_periods`）

listener observation 的 `match.kind` 除 `parsed_frame` / `frame_query` 外，还有两个**复用既有能力、不新建索引**的语义查询：`trace_query` 复用 `TraceService.run_replay`（并发抄表、单表、00A1、0020、0008 的多跳通信流）；`minute_periods` 复用 `list_task_minute_periods`（分钟采集，**禁止通过 raw HEX 猜测**）。

```json
{"source":"listener", "target":{"index_id":"idx-20260630-a"},
 "window":{"mode":"time_range","start":"00:00:00.000","end":"00:05:00.000"},
 "match":{"kind":"trace_query", "scope":"round",
   "feature":{"app_id":"0003","msg_seq":"1EC2","frm_type":"终端主动并发抄表",
              "dst_tei":"087","nid":"00947F69","channel":"载波",
              "app_raw_contains":"123456789012","raw_hex_contains":"123456789012"},
   "directions":["downlink","uplink","ack"]},
 "completion":{"match_count":1}}
```

- `feature`：`app_id` 必填；`scope` 为 `flow`/`round`/`campaign`；`directions` 只做 L2 展示与计数筛选，同一通信流默认保留必要 ACK 和对端帧。
- `raw_hex_contains` 对整帧 `raw_hex` 验证、`app_raw_contains` 对已解析应用载荷验证；前者**仅作末端验证**，删空白后须为偶数长度 2–512 个十六进制字符，**无 `app_id`/NID/时间窗/帧 ID 窗口任一收窄条件时 422**。
- `minute_periods`：`match` 给 `task_no`（必填）/`period_minutes`/`cco_tei`/`nid`，窗口仅 `time_range`；业务归属**以 `freeze_time` 为准**，L2 同时给 `log_time` 与 `freeze_time`，不得用上报时间替代。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

### §3.7 v1 专家/兼容路径

v1 语义：每接口校验 **scope + resource**；长任务返回 `operation_id` 轮询到终态；幂等同 v2；烧录强制 `firmware_roots` 白名单。

| 能力 | 端点组（前缀 `/api/ai/v1`） | scope |
| --- | --- | --- |
| 全局状态 / 审计 | `GET /status`、`GET /audit` | `status:read` |
| 模块会话 | `POST /module-sessions/ensure`、`{id}/stop`、`{id}/send` | `module_session:ensure` / `:stop` / `module_send:execute` |
| 烧录 | `POST /flash-operations`（202） | `module_flash:execute` |
| 侦听台控制 / 追踪 | `POST /listener/ensure`、`/listener/stop`；`GET /listener/schema`；`POST`/`GET /listener/traces[/{id}]` | `listener:ensure`/`stop`、`evidence:read`、`listener:trace` |
| 观察 | `POST /observations`（202，支持 `Idempotency-Key`） | `observation:create` |
| 操作与证据 | `GET /operations/{id}[/wait·/cancel]`、`GET /artifacts/{id}[/content]` | `evidence:read`（cancel 需 `observation:create`） |
| 帧索引 / 分钟分桶 | `GET /listener/indexes`、`/{id}/frames[/{frame_id}]`、`/listener/minute-periods` | `evidence:read` |
| 模拟集中器 | `POST /simcon/verify`、`/simcon/step`、`/simcon/open`/`close`；`GET /simcon/frames`、`/simcon/session`、`/simcon/store/events`、`/simcon/store/snapshots[/{id}]` | `simcon:verify` / `simcon:send` / `simcon:read` |

v1 专家 checklist（逐步控制串口或维护旧客户端时才用）：`POST /admin/grants` 拿 token（人做）→ `GET /status` 确认后端就绪与串口在线 → `POST /module-sessions/ensure` → `POST /flash-operations`/`POST /observations`/`POST /simcon/verify` → `GET /operations/{id}/wait` 到终态 → `GET /artifacts/{id}/content` 取证据正文 → 收尾 `POST /module-sessions/{id}/stop`、`/listener/stop`、`/simcon/close`。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

## §4 证据

### §4.1 观察任务语义（先建观察，再制造事件）

最小链：`POST /api/ai/v1/observations` → `GET /operations/{id}/wait?timeout_seconds=30` → `GET /artifacts/{artifact_id}/content`。**时序是关键**：module_log 观察只盯"创建时刻之后"的新日志——先建观察，再制造目标事件。

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/observations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "source":"module_log",
    "target":{"session_id":"<session_id>"},
    "window":{"mode":"live","start":"now","timeout_seconds":180},
    "match":{"kind":"literal","value":"<要找的字符串>","case_sensitive":false},
    "context":{"before":20,"after":30},
    "client_request_id":"<id>"
  }'
```

幂等：`client_request_id` 缺省时取请求头 `Idempotency-Key`。**match 矩阵**（叶子 3 + 复合 2）：

- 叶子：`literal`（value 非空 ≤512 字符，带 `case_sensitive`）、`regex`（≤256 字符）、`loghook_rule`（`rule_id` 须是该模块的 module_log 规则，**从 `GET /api/dict/rules` 查**，无鉴权）。
- 复合：`sequence`（`steps` 叶子×1–16 + `max_interval_ms` 1–3600000，按顺序出现）、`not_seen`（`matcher` 叶子；仅**闭合窗**未出现才判 pass，live 窗到期且无可信到达时间 → `inconclusive`）。

| window.mode | 参数 | 约束 |
| --- | --- | --- |
| `live` | `timeout_seconds` 1–3600 | 只盯创建之后的新事件 |
| `time_range` | ISO 8601 `start`/`end` | 须落在当前内存日志边界内 |
| `cursor_range` | `start_seq`/`end_seq` | 回放既有区间，跨度 ≤10000 行且区间已闭合 |

**侦听台帧观察（source=listener）**：

```bash
-d '{"source":"listener",
     "target":{"mapping_id":"listener","capture":"current"},
     "window":{"mode":"live","timeout_seconds":180},
     "match":{"kind":"parsed_frame","frame_kind":"central_beacon","selector":"first"}}'
```

- `match` **必填**（缺省直接 422），kind 仅 `parsed_frame` / `frame_query`；过滤三件套 `frame_kind`（当前仅 `central_beacon`，留空=任意）、`where`（`{"path":"analysis.full.<字段>","op":"eq","value":...}`，op 目前仅 eq）、`selector`（first/last/all/first_per_minute/nth）。
- `mapping_id` 用 `listener`（不是 `listener-main`）；字段路径先 `GET /api/ai/v1/listener/schema` 确认；window 同样支持 time_range / cursor_range（须给 `index_id` + `start_frame_id`/`end_frame_id`，跨度 ≤500 帧）。

> 来源：ai-control-plane/references/observations.md；ai-control-plane/references/operation-guide.md

### §4.2 证据落盘与 operation 状态机

- `wait` 命中 → `state=matched`；`result.snippet` 含命中上下文行，`result.log.artifact_id`（`art-xxx`）**即证据句柄**；`GET /artifacts/{id}` 看元数据、`/content` 取正文。取消 `POST /operations/{id}/cancel`（**烧录类不可取消**）。
- 状态机：`created → waiting → matched / succeeded → timed_out / cancelled / error / source_stopped / interrupted`；`interrupted` 是服务重启时未完成操作的自动标记（持久化 `<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json`）。
- **落盘自检**：① 每条结论都要能指到一个 `artifact_id` 或 `ref=listener:<index_id>:<frame_id>`，不能只写"看到了"；② 历史证据必须带 `index_id`，跨索引关联一律不采信；③ 不把 raw_hex/原始日志整段复制进上下文或报告，只给 ref 与必要片段（L1 优先）；④ 全链路验证的落盘位置是 `GET /api/run/{id}/report`、`/artifacts`、`/artifacts/{artifact_id}`（有路径越界防护）。
- **三种"看起来成功"的坑**：job `succeeded` 只代表任务跑完（业务结论另看 summary/verdict）；`verification_run` summary 写 `fail (0 pass/1 fail)` 时不得写"验证通过/烧录成功"；live 窗 `not_seen` 判 `inconclusive` 时只能报"未观测到，证据不足"。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/observations.md；ai-control-plane/references/api-contract.md

## §5 编排与页面

### §5.1 验证编排 REST（无鉴权，可选）

```bash
curl http://127.0.0.1:8790/api/scenarios               # 场景模板清单（/api/scenarios/<id>[/task]）
curl -X POST http://127.0.0.1:8790/api/run \
  -H "Content-Type: application/json" -d '<RunRequest，字段见 apps/workbench/orchestration/dto.py>'
# → 立即返回 run 视图（status=running），轮询 GET /api/run/<run_id> 到终态
#   passed / failed / cancelled / error / inconclusive
# 报告 GET /api/run/<id>/report；产物 GET /api/run/<id>/artifacts[/{artifact_id}]；取消 POST /api/run/<id>/cancel
```

- 其余：`GET /api/runs?limit≤200`（历史）、`POST /api/compare`、`POST /api/feedback`（比对/归因，不落 Run）。整链是烧录→监控→激励→比对→反馈→报告。
- 与 AI 控制面的取舍：要**授权审计/证据链/幂等**走 `/api/ai/v1`；只是**直接驱动一次全链路验证拿报告**，`/api/run` 更短（无 token、无 operation）。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/features.md

### §5.2 前端调用方映射（页面 → API 组 → 前缀机制）

| 前端文件 | 调用组 | 前缀机制 |
| --- | --- | --- |
| `pages/listener/{app,frames-pro}.js` | 侦听台日志/帧/串口/fs | **硬编码** `/api/listener/...`（独立版同逻辑硬编码 `/api/...`，两副本并存） |
| `pages/trace/trace.js` | 通信流追踪 + 帧详情 + indexes | 硬编码，注意双前缀 |
| `pages/dict/dict.js`、`pages/scenario/scenario.js`、`workbench.html` | 协议字典 / 编排 | 硬编码 `/api/dict`、`/api/...` |
| `pages/simcon/simcon.js` | 模拟集中器 + 构帧预览字典 | 硬编码 `/api/simcon` |
| `pages/module-serial/module-serial.js`（两副本） | 模块日志 + `/fs/*` + `/loghooks/*` | `API_BASE = body[data-api-base] ?? "/api"` ＋ 路径自带 `/module-serial` 命名空间 → 两形态通用 |
| `pages/serial-profile/serial-profile.js` | 串口 Profile | `API_BASE`（`/api`） |
| AI agent（无页面） | v2（默认）/ v1（专家兼容） | 直连 8790 `/api/ai/v2`；需要旧细粒度能力时 `/api/ai/v1` |

> 来源：ai-control-plane/references/api-contract.md

### §5.3 与页面操作的关系

AI 控制面复用与页面**同一套后端服务**（`ModuleSerialService` / listener service）：串口同一时刻独占，**页面与 AI 不能同时开同一串口**（409）。ADR-27 修的前端 bug（`ms-refresh-speed` 缺失导致实时日志页无反应）**不影响 API 行为**；主题/保活只影响页面观感（§8 G1/G2），与 AI 调用面无关。

> 来源：ai-control-plane/references/operation-guide.md

## §6 契约红线（完整版）与通用约定

### §6.1 通用约定

- Base `http://127.0.0.1:8790`；v2 默认 `/api/ai/v2/*`。本机 `WORKBENCH_LOCAL_FULL_ACCESS=1` + 真 loopback 可用 v2 全能力（免 token）；局域网或 v1 业务接口需 `Authorization: Bearer <token>`（**不要把 token 写进输出、日志或提交内容**）。
- 探活：`GET /api/health`（免鉴权）；能力发现 `GET /api/ai/v2/capabilities`；v1 专家状态 `GET /api/ai/v1/status`（带 token）。
- 幂等：v2 写操作一律带 `client_request_id`，重复提交复用原 job；v1 也支持 `client_request_id`（或 `Idempotency-Key` 头）。
- 长任务：v2 返回 `202` + `job_id`（`GET /api/ai/v2/jobs/{job_id}` 读）；v1 返回 `operation_id`（`GET /api/ai/v1/operations/{id}/wait?timeout_seconds≤30`）。
- 统一错误响应（D-04）：`{code, message, details, request_id}`，兼容旧 `detail` 字段。
- 侦听台深度解析三档 `parse_backend`（local/remote/none，REQS-0019）：`none` 时帧仍可查但无深度字段，先起 Windows 解析网关——**仅 Windows 侧、由人执行**（桌面 `wsl环境部署.bat` → [4]，或 `powershell -File tools/scripts/uart-map.ps1 -Action start-gateway`，相对 `<WORKBENCH_ROOT>`）。

> 来源：ai-control-plane/references/api-contract.md

### §6.2 行为红线（8 条，完整表述）

1. **授权归人、scope 最小化**：`admin/grants` 只由人本机执行（127.0.0.1 + admin key）；AI 只使用已有 token，不自签、不扩权、不转交。只申请本次任务需要的 scope（§2.2），能不给 `resources:["*"]` 就不给。
2. **用完即止**：完成本次任务即停——不开任务外的会话、不跑任务外的验证、不做"顺手"的全流程；结束前把本次开的会话/采集/串口收尾（§3.7）。
3. **串口独占**：同一物理串口同一时刻一个持有者（AI 与前端共享规则）；开了就关（stop/close 释放；v2 stop 卡 waiting 时以物理串口释放为准）；409 时等待或换口，**不硬抢、不并发重试**。
4. **开串口前先 preflight**：先 `/api/serial-bridge/status` + `/verify`；`workbench_ready=false` 时不许 ensure/open（细节见 `wb-serial`）。
5. **观察先建后造**：先 `observations` 再制造目标事件；module_log 只盯创建之后的新日志，事后补观察等于没观察。
6. **不可取消的操作耐心等终态**：烧录/verify 不并发重试（v2 `flash-jobs`/`verification-runs`，v1 `flash-operations`/`simcon/verify`）。simcon verify 默认 240s 总看门狗（`WORKBENCH_VERIFY_TIMEOUT_S` 可覆盖），超时落 `error` 并复位运行守卫，后续提交不会再被 409 永久拒绝。
7. **禁用 `pkill/pgrep -f` 匹配自身**：`pkill -f "workbench.run"` 会命中执行该命令的 shell 自身（bash -c 命令行含明文串），误杀自身；停止工作台先 `pgrep -af "[w]orkbench.run"` 取 PID 再 kill，或直接终止受管后台任务。
8. **agent 沙箱禁用 nohup 常驻**：nohup 子进程随外层 shell 结束被回收（实测），必须用受管后台任务常驻；桌面/WSL 人机环境才可用 nohup。

### §6.3 契约红线（改接口/改页面时的检查清单）

1. **改任何路由/字段：先改后端 → 同步 `docs/api-contract.md` → 跑 `apps/workbench/test_*.py` 契约测试**。
2. **双前缀特例**：workbench 下 listener 的 traces/indexes 是 `/api/listener/listener/*`，别"顺手修正"成单前缀。
3. **双副本同步**：页面在 `apps/<pkg>/static/`（独立版）与 `apps/workbench/static/pages/<pkg>/`（嵌入版）**必须同时存在**；改 JS/CSS 两份都改并**同一 commit 提交**（一键启动用 `git archive HEAD`，未提交改动不生效）。
4. **simcon 帧列表响应键是 `entries`**（含 `counts`/`next_after_seq`/`has_more`），不是 `frames`。
5. **异步端点返回 202 + 轮询**：`logs/open`、`serial/start`、`module-serial start/flash`、AI `flash/observation/trace/simcon-verify`、`POST /api/run`；前端必须实现轮询与取消。
6. **409 是资源冲突**（串口占用/互斥），不是错误——UI 提示而非报错弹窗；同一规则适用于 AI。
7. **字典/规则端点直接读 `libs/` 真文件**（`libs/parser_lib/adapters/*/metadata/*.json`、`libs/loghooks/rules/`、`libs/case_library/data/cases.json`）——**改 JSON 即改端点输出**（无拷贝层）。
8. **AI 控制面：新接口必须声明 scope；烧录类必须走 `firmware_roots` 白名单；幂等键 `client_request_id` 全程携带**。
9. **v2 是默认低 token 任务入口；v1 保持专家兼容**，不得因库存收敛而删除或改名。
10. **主题（REQS-0012）**：`html[data-theme]` + `--theme-registry` 单一数据源；新增主题只改 `tokens-v2.css` 一处；iframe 内页面需带防闪跳 boot 脚本与 `wb-theme-change` 监听。

> 来源：ai-control-plane/references/api-contract.md

## §7 错误码速查（常见错误 → 原因 → 处置）

| 码 | 含义 | 常见具体原因 | 处置 |
| --- | --- | --- | --- |
| 401 | 缺 token / 无效 / 过期 / 已撤销 | v2 `capabilities` 401「缺少 Bearer token」= 启动漏了 `WORKBENCH_LOCAL_FULL_ACCESS=1` 或非真 loopback；v1 业务端点即使 local_full 也要 token | v2 按 §1.2 重启；v1 按 §2 找人签发，别自签 |
| 403 | 越权 | scope/resource 不匹配；固件路径不在授权 `firmware_roots`（"未配置允许烧录目录"）；非本机发授权；L3 ref 不属于本 job | 补 scope / 换带 `firmware_roots` 的授权 / 只用本 job 的 ref |
| 404 | 资源不存在 | 会话、operation、Artifact、索引、场景 task 文件缺失 | 校验 id 与索引是否存在；场景 task 缺失是已知缺口（§8） |
| 409 | **资源冲突，不是故障** | 串口被页面/AI 占用；串口采集与日志索引互斥；观察活跃时普通 stop；幂等冲突；verify 运行守卫 | 等待、换口或 `force:true`；不并发重试；不做排障式排查 |
| 422 | 请求体校验失败 | `match` 非法/缺失；`window.mode` 写了 `historic`（只支持 live/time_range/cursor_range）；`minute_periods` 缺 `task_no`；`raw_hex` 无收窄条件；ref 格式错或 >10 个；超时越界 | 按 §3.6/§4.1 的合法取值改写，别靠重试 |
| 503 | 后端不可用/未配置 | admin key 未配置或未重启；串口未启用；侦听台不可用；解析不可用 | 配置/重启对应后端；解析不可用时改走原始帧查询并标注 |
| 501 | 非 Windows 原生文件选择 | 在非 Windows 侧调用原生文件对话框 | 改用 API 传路径参数 |

定位顺序：先看响应体 `{code, message, details, request_id}`，再对照本表，**不要凭状态码猜业务原因**；仍走异步的 error 原因去 `<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json` 查该 op 的 `error`（evidence 可能全空，见 §3.4）。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/auth.md

## §8 已知缺口

| # | 缺口 | 位置 | 影响 | 现状/绕法 |
| --- | --- | --- | --- | --- |
| G1 | `refreshFrames` 空结果分支 `var body` 声明在使用之后（var 提升为 undefined），`body.querySelector` 抛 TypeError 被静默 `.catch` 吞掉 | `apps/workbench/static/pages/simcon/simcon.js:271-277` | 空会话/过滤无结果时列表停在"加载中…" | **2026-08-31 已修复**（`var body` 上移），留作审核记录 |
| G2 | 保活 iframe 切主题不实时跟随：外壳 `switchTheme` 对所有 iframe `postMessage({type:"wb-theme-change"})`，但只有 module-serial/maintenance/serial-profile 三页装了监听 | `pages/trace\|dict\|scenario\|simcon`、`pages/listener/index.html`、`workbench.html` | 已打开页签保持旧主题直到重载 | **2026-08-31 已修复**（六页补监听，9 个保活子页全部跟随） |
| G3 | `join_anhui` / `open_close` / `search_meter` 三个场景 `tasks/*.json` 缺失 | 编排场景模板 | `GET /api/scenarios/{id}/task` 404 明确报错，页面红条提示 | 端点行为正确，缺的是模板文件；换可用场景 |
| G4 | 侦听台依赖 C# DLL/pythonnet，缺失时挂载降级；`parse_backend=none` 时缺解析字段 | workbench 挂载层 / 侦听台解析后端 | `listener_mounted=false`、`/parse` 降级 503、`parse_unavailable` | 采帧与索引照用，不把未解析帧归入业务分类；要字段就起 Windows 解析网关（仅人执行，§6.1） |
| G5 | `.md` 路由表不被库存脚本校验 | `verify_api_inventory.py` | 只校验 v2 8 条路由命名 schema、AI 能力映射、listener schema 能力位 | 改接口时按 §6.3 第 1 条人工同步文档并跑契约测试 |

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/features.md；ai-control-plane/references/operation-guide.md

---

## 附录 · 深水事实库（按节读，不复制）

精确契约在入口技能事实库：`auth.md`(43) 授权原文、`features.md`(119) 能力全表、`observations.md`(72) 观察语义、
`api-contract.md`(491) §1/§2/§6/§6.1/§7/§10/§11/§12、`operation-guide.md`(520) §1/§2/§3/§7/§11–§15。
旧门面归档：`_归档-门面v2.9.md`(257)，仅当新文档查不到时参考。
> 路径前缀：ai-control-plane/references/
