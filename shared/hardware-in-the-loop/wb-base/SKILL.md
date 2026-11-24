---
name: wb-base
description: 共享基座子技能：工作台在线任务的接入与授权（路径根解析、部署形态与前缀映射、平台端点、启动配置、grant/scope/resource/token）、v2 任务门面（能力清单与源健康、四步任务流、job 与证据读取、v1 专家兼容）、证据口径（L1/L2/L3、观察任务语义、证据落盘）、契约红线与错误码速查。任何在线任务开始前读本技能。
argument-hint: "[任务，如 拿 token / 看 capabilities / 读 job 证据 / 查错误码]"
metadata:
  author: reasonix
  version: "1.1.0"
  applies-to: 任意工作区（<WORKBENCH_ROOT> 按序单点解析见 §1.1）
  source: 拆自 ai-control-plane（2026-10-28）；2026-11-18 拆薄：低频内容下沉 references/（v2 契约补充/scope 全表+v1 面/挂载语义/语义查询/观察语义全文/编排与页面/G 缺口），正文只留每次必用+红线+错误码
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
| 建观察任务要 match 矩阵/完整示例 | references/observations.md |
| 旧客户端/专家诊断要细粒度端点 | references/scopes.md |
| 判"这条结论算不算证据""为什么是 inconclusive" | 本技能 §4 |
| 只想跑一次全链路验证拿报告（无 token）/ 排查前端调用 | references/orchestration.md |
| 401/403/404/409/422/503 怎么处置 | 本技能 §7 |
| 烧录固件并判定是否真烧成 | `wb-flash` |
| 侦听台建索引、查已解析帧、通信流追踪、组网诊断 | `wb-listener` |
| 模拟电表 645 从站调测 | `wb-simeter` |
| 模拟集中器验证/单步/并发抄表/档案 | `wb-simcon` |
| 开串口前的 serial-bridge preflight、模块串口会话 | `wb-serial` |

> 来源：ai-control-plane/SKILL.md

## §1 接入

### 前言：部署形态与前缀映射（一句话版）

- **入口**：统一工作台 `apps/workbench/run.py` → **8790**（`/api/*` 各命名空间、页面 `/static/pages/<页名>/`）；独立版：侦听台 8765、simcon 8781。**module_log 独立版已并入工作台 `/module-serial`；8766 现为 Windows 宿主控制面（§1.4），勿再拉起占用。**
- **双前缀特例（勿"修正"）**：外部路径 `/api/listener/listener/traces` 是正确的，不是 bug。
- 挂载代理语义、剥前缀规则、挂载降级 → `references/deployment.md`（排查挂载/改接口时才读）。

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

### §1.2 启动与配置（2026-11-18 起：systemd 常驻为主路径）

**主路径（WSL systemd 常驻，已实测）**：单元文件 `/etc/systemd/system/zzt-workbench.service`（`Restart=always`，环境变量已带 `WORKBENCH_LOCAL_FULL_ACCESS=1`、`HPLC_OPEN_WORKBENCH=0`），开机随 WSL 自启、崩溃/SIGTERM 自动拉起。

- **停止只能 `systemctl stop zzt-workbench`**；直接 kill 会被秒拉起。
- **禁止手工 `python -m workbench.run` / `run.py` 起第二份**（端口冲突导致 restart 循环）；启动权归 systemd。
- 冷启动约 11 秒，stop/start 后等一会儿再探活；日志 `journalctl -u zzt-workbench`。

```bash
systemctl status|stop|start zzt-workbench   # 唯一控制入口
journalctl -u zzt-workbench -n 50           # 日志
curl -s http://127.0.0.1:8790/api/health    # 探活
```

**备选（无 systemd 的环境才用）**：手工启动要带 `WORKBENCH_LOCAL_FULL_ACCESS=1`（漏掉则 v2 `capabilities` 直接 401「缺少 Bearer token」，AI 会误以为要找人要 token 而绕路）：

```bash
WORKBENCH_LOCAL_FULL_ACCESS=1 HPLC_OPEN_WORKBENCH=0 \
  nohup python3 <WORKBENCH_ROOT>/apps/workbench/run.py > /tmp/wb.log 2>&1 &
```

- agent 沙箱/容器（子进程随外层 shell 结束被回收）必须用受管后台任务，日志从该任务输出读；桌面/WSL 人机环境才可用 nohup。
- 停止禁用 `pkill -f "workbench.run"`（会命中执行该命令的 shell 自身导致自杀）；先 `pgrep -af "[w]orkbench.run"` 取 PID 再 kill（有 systemd 时一律 systemctl）。
- **授权管理密钥**（AI 自签 grant 时需要）：启动前设 `WORKBENCH_AI_ADMIN_KEY`（systemd 单元已含）；未配置时 admin 授权接口返回 `503 未配置人工授权管理密钥`。页面操作不需要它。
- **一键启动包**用 `git archive HEAD` 打包：**未提交的改动不生效**（改页面/后端先提交再打包）。

### §1.4 Windows 宿主控制面（8766，串口/网关/诊断的唯一开关口）

> **维护口径（2026-11-18）**：WSL 侧 `wsl-control.py` **v2.0.0 为唯一权威**（`/api/v1/*`、audit、workbench 探活，响应包一层 `data`）；Windows 侧旧文档 `WSL-CONTROL-API.md`（v1）已过时，仅存档。要 Windows 侧手动开关工作台，在 v2 里加路由即可（systemd 已兜底，非必须）。

Windows 侧三件事（串口桥、解析网关 8700、海思诊断服务 8765）由常驻服务 `wsl-control` 统一管；
**技能不要再手动 `wsl stop`、不要自己找 COM、不要直接杀进程**，一律走它。

```bash
HOST=$(ip route show default | awk '{print $3}')
TOKEN=$(cat /mnt/c/Users/*/.wsl-control/token 2>/dev/null | tr -d '\r\n')   # 令牌文件也可能在 C:\Users\Public 下

curl -s -H "X-Host-Token: $TOKEN" http://$HOST:8766/api/v1/status          # 看板数据（缓存 8s）
curl -s -H "X-Host-Token: $TOKEN" http://$HOST:8766/api/v1/ports           # 逐口：COM/归属/通道
curl -s -X POST -H "X-Host-Token: $TOKEN" http://$HOST:8766/api/v1/services/bridge/{start|stop|restart}
curl -s -X POST -H "X-Host-Token: $TOKEN" http://$HOST:8766/api/v1/ports/<id>/{enable|disable}
curl -s -X POST -H "X-Host-Token: $TOKEN" http://$HOST:8766/api/v1/doctor  # 出问题先跑它
```

- **令牌**：非回环必须带；回环（Windows 本机）免。令牌文件 `%USERPROFILE%\.wsl-control\token`。
- **归属**：`ports[].owner` = `serial-bridge` / `fc-diag` / `free` / `absent` / `disabled`；`conflict=true` 表示桥与诊断服务抢同一 COM。
- **让口**给 Windows 工具：`services/bridge/stop`（全部）或 `ports/<id>/disable`（单个，会重启 Windows 桥 5–15s）。
- **看板**：`http://127.0.0.1:8766/`（Windows 本机）；从 WSL 打开需粘贴令牌。
- **usbipd 已移除**（2026-11-17）：`/api/usbipd/*` 返回 410，不要再提 attach/detach。

> 来源：/01-workfile-ai/01-zzt/ZZT_SELF/tools/win_host/WSL-CONTROL-API.md、README.md

## §2 授权：grant / scope / resource / token

### §2.1 边界与签发（对话授权后可自执行）

**授权在对话，签发可自执行**：用户明确说"允许 / 可以烧 / 直接升"即为授权；拿到授权后 AI 可自行签发**最小权限 grant**（仅本次任务 scope + 必要 `firmware_roots` + 短 TTL，建议 ≤3600s），或复用已有 token，然后直接提交烧录/升级。仍禁止：无授权就签 grant、扩大 scope（能窄就不给 `resources:["*"]`）、把 token 写进日志/提交、转交他人、靠重启工作台塞 env 白名单绕过（审计会记 `authorization_source`）。

签发仅限 workbench 本机 `127.0.0.1` + `X-Workbench-Admin-Key` 请求头；前置是工作台已在 8790 运行（`curl http://127.0.0.1:8790/api/health` → 200）且已配置 admin key。

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/admin/grants \
  -H "X-Workbench-Admin-Key: <WORKBENCH_AI_ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"scopes":["observation:create","evidence:read"],"resources":["*"],"ttl_seconds":3600,"reason":"监控cco日志"}'
# → {"grant":{"grant_id":"grant-...","scopes":[...],"resources":[...],"expires_at":"...","firmware_roots":[...]},"token":"xxxx"}
```

- **scope 最小化**：只申请本次任务需要的（§2.2），上面的例子就是"只监控日志"的最小集。`resources` 取 `*` 或具体 `mapping_id`/`session_id`；`ttl_seconds` 1–86400；`max_operation_seconds` 可选（默认 1800）。
- **要烧录必须给 `firmware_roots`**（允许的固件目录白名单数组），否则（v1 / 局域网面）flash 返回 **403「当前授权未配置允许烧录目录」**。
- **白名单两来源（2026-10-28 `d5719b7` 起 v1/v2 统一）**：`grant.firmware_roots` 优先 → 回退环境变量 `WORKBENCH_AI_FIRMWARE_ROOTS` → 都空则 403。`local_full`（本机 loopback 免 token）下没有 grant，白名单由 env 顶上；**没配 env 就 403**。放行时写 `store.audit(action="flash.authorization")`，记 `authorization_source`（grant/env/local_full_env）+ `bin_path` + 命中的 root。**团队红线：烧录必须先有用户明确授权**；授权后 AI 可自签带 `firmware_roots` 的 grant，但不得靠重启工作台塞 env 给自己开白名单（那条路没有 `flash.authorization` 审计）。
- `token` **只返回一次**（服务端只存 SHA-256 摘要）——务必当场保存，AI 全程只用 token。`503` = admin key 未配置/没重启；`403` = key 错或非本机发起。

> 来源：ai-control-plane/references/auth.md；ai-control-plane/references/operation-guide.md
> 来源：validation-20261028/F5（T4 实机：v2 `local_full` 零授权、无 `firmware_roots` 也烧成 STA）

### §2.2 scope 名单速览（14 种）与 resource 约定

- **速览**：`status:read`；`module_session:ensure`/`:stop`、`module_send:execute`、`module_flash:execute`（另需 `firmware_roots`）；`listener:ensure`/`:stop`、`listener:trace`；`observation:create`、`evidence:read`；`simcon:verify`/`:send`/`:read`；`simeter:read`。**scope→能力→所需资源全表 → `references/scopes.md`**。
- **资源（resource）**：串口类用 `serial_ports.json` 的 `mapping_id`：`cco-main`、`sta-main`、`listener`（实际 COM 号随接线变化，**调用方优先用 mapping_id，不硬编码 COM 号**）；simcon 口的 task **必须显式 `mapping_id:"simcon"`**（不传会自选 `/dev/ttyS0` 报 `Input/output error`，见 `wb-simcon` §1；该口实测 115200，baud 以 status 的 `mapping.baudrate` 为准）；会话资源用 `session_id`（`ms-xxxx`），AI 接口内部归一到其 `mapping_id`。`resources:["*"]` 全放行（谨慎）；越权 403，token 无效/过期/撤销 401。

> 来源：ai-control-plane/references/auth.md；ai-control-plane/references/operation-guide.md；ai-control-plane/references/simeter.md

### §2.3 token 用法与两条访问通道

- 请求头固定 `Authorization: Bearer <token>`；**不要把 token 写进输出、日志、提交内容或证据正文**。
- **v2（默认低 token 面）**：仅在**真实对端为 loopback**（`127.0.0.1`/`::1`）且显式设置 `WORKBENCH_LOCAL_FULL_ACCESS=1` 时进入 `local_full`、免 token，但仍写审计；局域网请求必须 Bearer grant，并按 capability、scope、逻辑资源 alias 过滤。
- **v1（专家兼容面）**：所有业务接口都要 Bearer token——**即使 `local_full` 也一样**（如 `GET /api/ai/v1/listener/indexes`）。admin grant 签发/撤销永远要本机 + admin key。
- **管理辅助**：`GET /api/ai/v1/admin/grants`（列，admin key）、`POST /api/ai/v1/admin/grants/{grant_id}/revoke`（撤销，404）、`GET /api/ai/v1/audit`（审计流水，token + `status:read`，按授权 resources 过滤）。**audit 翻页口径（2026-11-18 实测）**：响应键是 `entries`（不是 `events`/`items`）；小 `limit`（10/20）按时间正序翻出来的可能是几个月前的旧账，**要覆盖近期必须给大 `limit`（实测 500 才够今天）**，且 v1 即使 `local_full` 也要 Bearer。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/auth.md；ai-control-plane/references/operation-guide.md

## §3 任务门面 v2（默认 AI 调用面）

v2 把"查状态、并行观察、模块动作、验证、烧录、取证"收敛为任务级工作流：AI 客户端默认只需要**发现能力、提交一个任务、读取 job、按需取证**四类调用。v1 路由保留给专家诊断和兼容场景，**不因 v2 上线而删除或改名**。

### §3.0 执行层 CLI（首选执行方式）

本技能自带 `scripts/wb.py`（Python 3 标准库，无依赖）：把 §1/§2/§3 的高频判据固化成命令，**AI 首选跑它；下文 curl 序列降级为契约参考与脚本不可用时的兜底**。

| 命令 | 固化的判据（不再靠 AI 记） |
| --- | --- |
| `wb status` | 8766 owner/conflict + 8790 探活 + 桥 `all_enabled_ready`/`config_stale` 一屏 |
| `wb preflight <mapping_id>` | 只验目标口；`usable` 过线；`in_use=true` 不阻塞；全局 `ok` 不作数 |
| `wb auth --scopes … --firmware-root …` | 最小 scope + 烧录白名单 + token 只显示一次（--json 也遮蔽） |
| `wb session ensure <cco\|sta> --mapping …` | 显式 mapping_id（红线：不自动选口）；409=占用，提示不硬抢 |
| `wb flash submit <iap_*.bin>` | 只认 iap 件；幂等键默认 md5 派生（同件重提复用同 job，防二次烧录，§6.2 红线 6 由入口保证）；403 按"授权来源"解释，不引导重启塞 env |
| `wb wait <job_id>` | 轮询 ≤30s 到终态；**失败自动归因**（①steps.reason → ②sent_hex 空=没发出去 → ③L1 → ④operations.json，即 §3.4 口径） |
| `wb evidence <job_id> --level L1` | 三级证据读取 |

- 环境变量：`WORKBENCH_BASE`（默认 8790）、`WORKBENCH_AI_ADMIN_KEY`、`WORKBENCH_AI_TOKEN`、`WORKBENCH_ROOT`（解析序同 §1.1）。
- 退出码：0 成功；1 判定不过/任务失败；2 用法错误；3 连不上/缺配置（提示指向对应节）。
- 冒烟测试：`python3 scripts/test_wb.py`（内置模拟工作台，18 例覆盖 preflight usable 判定/会话 409/幂等键/失败归因/token 遮蔽/`flash run` 全链）。

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

### §3.2 verification-runs 的 body 形状（可直接复制）

v2 只认 `{"task": {…}}`，`task` 里装的是 v1 verify 的整个 body：

```json
{"task": {"mapping_id": "simcon",
          "profile": "anhui",
          "steps": [{"name": "s1", "send": {"afn": "10", "fn": "F1", "params": {}}}],
          "client_request_id": "v-001"},
 "client_request_id": "vr-001"}
```

- 把 v1 平铺字段写在上层（顶层 `id`/`profile`/`steps`）会 **422 `Extra inputs are not permitted: id/profile/steps`**——**v1 平铺写法的字段一个都不能带上来，连 `id` 也不行**。
- `task.mapping_id` 必给（`simcon`/`cco-main`/`sta-main`）；不给会走自动选口、掉到 `/dev/ttyS0` 报 `Input/output error`（见 `wb-simcon` §1）。
- **八条公开路径全表**（端点 × capability 对照，含"观察可取消、烧录/验证拒绝取消"等语义）→ `references/v2-contract.md`。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md
> 来源：validation-20261028/F3（T3 实机：平铺 → 422；包 `task` → 202）

### §3.3 四步低 token 任务流

1. `GET /capabilities` 发现后端与逻辑资源 alias（§3.1），**不读也不猜物理 COM 号**。
2. 提交一个任务：观察 `POST /investigations`、模块控制 `POST /module-actions`、验证 `POST /verification-runs`（body 形状见 §3.2）、烧录 `POST /flash-jobs`。
3. `GET /jobs/{job_id}` 读统一状态（可 `wait_seconds` 阻塞）。
4. 只有需要细节时才 `GET /jobs/{job_id}/evidence?level=L1|L2|L3`。

一次并行观察（最多 3 个 observation：模块日志 + 侦听台历史索引）的完整请求体示例 → `references/v2-contract.md`。

- 返回 `202` + `job_id`。历史窗口完成后可立即读 job；live 窗口由服务端 worker 推进。
- **`job_state` 是执行状态，`verdict` 只用于 investigation 观察**（`pass/fail/inconclusive/error`）；module_action / verification_run / flash_job 的 `verdict` 恒 `null`，模块动作/验证/烧录成功**不会**伪装成业务 `pass`。
- `cleanup=owned_only` 只清理由本任务创建的资源，不关闭人工或 UI 复用的会话。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md

### §3.3b 找回最近的 job

`job_id` 丢了不用翻 json 文件：`GET /api/ai/v2/jobs?kind=flash_job,verification_run&state=error&limit=10` 列最近任务摘要（含派生 `job_id`），拿到 id 再 `GET /jobs/{job_id}` 或 `/evidence`。参数细节（`kind`/`state`/`since`/`limit` 上限、"列表未按资源收敛"的边界）→ `references/v2-contract.md`。

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

漏点/通信流追踪任务用：`match.kind` 还有 `trace_query`（复用 `TraceService.run_replay`，多跳通信流）与 `minute_periods`（复用 `list_task_minute_periods`，**禁止通过 raw HEX 猜测**）两个语义查询——复用既有能力、不新建索引。`feature` 字段表、收窄条件不足 422、业务归属以 `freeze_time` 为准等完整契约 → `references/semantic-queries.md`。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

### §3.7 v1 专家/兼容路径（详情下沉）

v1 语义：每接口校验 **scope + resource**；长任务返回 `operation_id` 轮询到终态；幂等同 v2；烧录强制 `firmware_roots` 白名单。端点组全表、scope 对照与专家 checklist（逐步控制串口或维护旧客户端时用）→ `references/scopes.md`。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md

## §4 证据

### §4.1 观察任务语义（先建观察，再制造事件）

**红线（时序关键）**：module_log 观察只盯"创建时刻之后"的新日志——**先建观察，再制造目标事件**，事后补观察等于没观察。最小链：`POST /api/ai/v1/observations` → `GET /operations/{id}/wait?timeout_seconds=30` → `GET /artifacts/{artifact_id}/content`。

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

幂等：`client_request_id` 缺省时取请求头 `Idempotency-Key`。**match 必填**（缺省直接 422）：叶子 `literal` / `regex` / `loghook_rule`（`rule_id` 须是该模块的规则，从 `GET /api/dict/rules` 查，无鉴权）；复合 `sequence`（`steps`×1–16 按顺序出现）/ `not_seen`（仅**闭合窗**未出现才判 pass，live 窗到期且无可信到达时间 → `inconclusive`）。

| window.mode | 参数 | 约束 |
| --- | --- | --- |
| `live` | `timeout_seconds` 1–3600 | 只盯创建之后的新事件 |
| `time_range` | ISO 8601 `start`/`end` | 须落在当前内存日志边界内 |
| `cursor_range` | `start_seq`/`end_seq` | 回放既有区间，跨度 ≤10000 行且区间已闭合 |

完整 match 矩阵、侦听台帧观察（**`mapping_id` 用 `listener` 不是 `listener-main`**、`frame_kind`/`where`/`selector`、window 参数）→ `references/observations.md`。

### §4.2 证据落盘与 operation 状态机

- `wait` 命中 → `state=matched`；`result.snippet` 含命中上下文行，`result.log.artifact_id`（`art-xxx`）**即证据句柄**；`GET /artifacts/{id}` 看元数据、`/content` 取正文。取消 `POST /operations/{id}/cancel`（**烧录类不可取消**）。
- 状态机：`created → waiting → matched / succeeded → timed_out / cancelled / error / source_stopped / interrupted`；`interrupted` 是服务重启时未完成操作的自动标记（持久化 `<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json`）。
- **落盘自检**：① 每条结论都要能指到一个 `artifact_id` 或 `ref=listener:<index_id>:<frame_id>`，不能只写"看到了"；② 历史证据必须带 `index_id`，跨索引关联一律不采信；③ 不把 raw_hex/原始日志整段复制进上下文或报告，只给 ref 与必要片段（L1 优先）；④ 全链路验证的落盘位置是 `GET /api/run/{id}/report`、`/artifacts`、`/artifacts/{artifact_id}`（有路径越界防护）。
- **三种"看起来成功"的坑**：job `succeeded` 只代表任务跑完（业务结论另看 summary/verdict）；`verification_run` summary 写 `fail (0 pass/1 fail)` 时不得写"验证通过/烧录成功"；live 窗 `not_seen` 判 `inconclusive` 时只能报"未观测到，证据不足"。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/observations.md；ai-control-plane/references/api-contract.md

（原 §5 编排与页面已下沉：全链路验证编排 REST 与前端调用方映射 → references/orchestration.md，AI 日常任务用不到。）

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

1. **授权在对话、签发自执行、scope 最小化**：用户明确授权后 AI 可自行签发最小权限 grant（本机 127.0.0.1 + admin key），也可复用已有 token；只申请本次任务需要的 scope（§2.2），能不给 `resources:["*"]` 就不给；不扩权、不转交、不把 token 写进日志/提交。
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
| 401 | 缺 token / 无效 / 过期 / 已撤销 | v2 `capabilities` 401「缺少 Bearer token」= 启动漏了 `WORKBENCH_LOCAL_FULL_ACCESS=1` 或非真 loopback；v1 业务端点即使 local_full 也要 token | v2 按 §1.2 重启；v1 按 §2 签发（用户授权后 AI 可自签）或复用已有 token |
| 403 | 越权 | scope/resource 不匹配；固件路径不在授权 `firmware_roots`（"未配置允许烧录目录"）；非本机发授权；L3 ref 不属于本 job | 补 scope / 换带 `firmware_roots` 的授权 / 只用本 job 的 ref |
| 404 | 资源不存在 | 会话、operation、Artifact、索引、场景 task 文件缺失 | 校验 id 与索引是否存在；场景 task 缺失是已知缺口（§8） |
| 409 | **资源冲突，不是故障** | 串口被页面/AI 占用；串口采集与日志索引互斥；观察活跃时普通 stop；幂等冲突；verify 运行守卫 | 等待、换口或 `force:true`；不并发重试；不做排障式排查 |
| 422 | 请求体校验失败 | `match` 非法/缺失；`window.mode` 写了 `historic`（只支持 live/time_range/cursor_range）；`minute_periods` 缺 `task_no`；`raw_hex` 无收窄条件；ref 格式错或 >10 个；超时越界 | 按 §3.6/§4.1 的合法取值改写，别靠重试 |
| 503 | 后端不可用/未配置 | admin key 未配置或未重启；串口未启用；侦听台不可用；解析不可用 | 配置/重启对应后端；解析不可用时改走原始帧查询并标注 |
| 501 | 非 Windows 原生文件选择 | 在非 Windows 侧调用原生文件对话框 | 改用 API 传路径参数 |

定位顺序：先看响应体 `{code, message, details, request_id}`，再对照本表，**不要凭状态码猜业务原因**；仍走异步的 error 原因去 `<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json` 查该 op 的 `error`（evidence 可能全空，见 §3.4）。

> 来源：ai-control-plane/references/operation-guide.md；ai-control-plane/references/api-contract.md；ai-control-plane/references/auth.md

## §8 已知缺口（G1–G5，明细下沉）

一句话版：G1/G2 已修复（留档）；G3 三个场景模板 `tasks/*.json` 缺失（换可用场景）；G4 侦听台/解析降级 `parse_backend=none`（要字段起 Windows 解析网关，仅人执行）；G5 `.md` 路由表不进库存校验（改接口按 §6.3 第 1 条人工同步）。明细与代码位置 → `references/known-gaps.md`。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/features.md；ai-control-plane/references/operation-guide.md

---

## 附录 · 深水事实库（按节读，不复制）

**本技能下沉件**（`references/`，按需读、不随任务常载）：

| 文件 | 内容 | 何时读 |
| --- | --- | --- |
| `v2-contract.md` | 八条公开路径全表、investigations 完整请求示例、找回 job 参数细节 | 提交/轮询任务拿不准形状时 |
| `scopes.md` | scope→能力全表（14 种）、v1 端点组与专家 checklist | 签非烧录类 grant、维护 v1 旧客户端 |
| `observations.md` | 观察 match 矩阵、侦听台帧观察完整参数 | 建观察任务 |
| `semantic-queries.md` | `trace_query` / `minute_periods` 完整契约 | 漏点/通信流追踪 |
| `deployment.md` | 挂载代理语义、剥前缀、双前缀特例、挂载降级 | 排查挂载/前缀、改接口 |
| `orchestration.md` | 编排 REST（`/api/run` 全链路）、前端调用方映射 | 无 token 跑全链路、排查前端 |
| `known-gaps.md` | G1–G5 明细 | 留档审计 |

**入口技能事实库**（更深的契约原文）：`ai-control-plane/references/` 下 `auth.md`(43) 授权原文、`features.md`(119) 能力全表、`observations.md`(72) 观察语义、
`api-contract.md`(491) §1/§2/§6/§6.1/§7/§10/§11/§12、`operation-guide.md`(520) §1/§2/§3/§7/§11–§15。
旧门面归档：`_归档-门面v2.9.md`(257)，仅当新文档查不到时参考。
> 路径前缀：ai-control-plane/references/
