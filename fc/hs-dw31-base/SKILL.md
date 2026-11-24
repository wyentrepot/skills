---
name: hs-dw31-base
description: 共享基座子技能：海思 DW31 调试唯一的 CLI（fcctl.py）与契约（contract.md / errors.md / 事件与 MCP 预留）。hs-dw31-upg / hs-dw31-diag / hs-dw31-nv 任何一个开始干活前必先读我，拿 $BASE、doctor 前置判定与产物落盘约定；直接要跑 fcctl.py、查服务端点/错误码/判据/重启 8765 控制面时也读我。仅限海思 DW31 工程；非海思工程、其他厂商芯片、工作台 8790 与 wb-* 系列、工装 645/376.2 不要用我。
argument-hint: "[拿 CLI / 查契约 / 错误码排障 / 落盘约定]"
metadata:
  author: reasonix
  version: 3.0.0
  applies-to: 海思 DW31 / 海思 PLC CCO/STA 工程（模块 DW31C；Windows FC 服务 8765）；不绑定绝对工作区
  source: 2026-11-12 接入；2026-11-17 重构为任务驱动；2026-11-18 补 8766 控制面与实测坑；2026-11-18 由单技能拆分为总分总五技能，本技能承载原 §1 路径 / §3 前置 / §5 落盘 / §7 维护规则与 contract.md、errors.md、events.md、mcp.md、scripts/fcctl.py
---

# 海思 DW31 调试基座（hs-dw31-base）

> 一句话：本技能是 hs-dw31 系列的**共享基座**——CLI（fcctl.py）、契约（contract.md）、前置判定与落盘约定都在这里；任务操作步骤在子技能里，本技能不装。

## 0. 何时读我

- **REQUIRED**：执行 `hs-dw31-upg` / `hs-dw31-diag` / `hs-dw31-nv` 任何任务前，先读本技能。
- 直接要跑 fcctl.py、查服务端点 / 错误码 / 字段判据 / 8766 控制面（重启 8765 / 让出 COM8 / 换宿主 DB）时读我。
- 判断是不是海思工程、决定加载哪个子技能：去元技能 `hs-dw31`，不在本技能。

**系列约定**：各子技能正文里的 `contract.md §x`、`references/errors.md`，一律指 `$BASE/references/` 下对应文件，不再重复写全路径。

## 1. 路径与 CLI（唯一规则：运行时解析，禁止写死）

| 名称 | 怎么得到 | 用途 |
|---|---|---|
| `$BASE` | 加载本技能时给出的技能目录（base directory） | `python3 $BASE/scripts/fcctl.py`；`$BASE/references/*.md`；命令里不要固化仓库绝对路径 |
| `PROJECT` | ① 用户给的路径 → ② `$HS_DW31_PROJECT` → ③ `fcctl status` 的 `prim.path` / `biz.dir` 反推 → ④ 从当前目录向上找 `scripts/build.sh` + `build/config/DW31v100` → ⑤ 仍不唯一就问用户 | 只读工程；编译与产物都在它下面 |
| `SERVICE` | `fcctl status` 的 `logfile` 等字段，或现场 `C:\fc_diag_client` | 服务自有文件（samples / 审计 / 帧日志）；**只读写服务自己的文件，不当工作区** |
| `REQ_DIR` | `PROJECT/reqs/<id>-<slug>/`（或会话工作区的 `reqs/<id>-<slug>/`） | 日志与报告落这里，见 §4 |

```bash
CTL="python3 $BASE/scripts/fcctl.py"
$CTL doctor
```

- 找不到 `PROJECT` 不影响只读取证（状态 / 帧 / 日志都走服务）；只有编译、选包、看工程配置时才需要它。
- **任何情况下都不要假定某个固定工作区路径存在**；也不要因为当前目录"不在某个路径下"就不加载本系列技能。

## 2. 通用前置（每个任务开始前跑一次）

```bash
$CTL doctor
```

- `data.selected=legacy` 且 `data.legacy.device_ready=true` → 继续。
- `device_ready=false` → 只做 `status`，按 `$BASE/references/errors.md` 处理；不发设备命令。
- `data.selected=null` → 停，让用户启动 Windows 侧 FC 服务；不要猜。

## 3. 基座级红线

1. **只用于海思工程**；非海思不操作设备。
2. **先读状态再写**：`start_running=true` 或 `port_open=false` 时停手。
3. **证据可追溯**：结论带帧 `id` / `ts` / `param_hex` 或 `nv_id` / `rc`，不编造解码值。
4. **高危写操作授权在对话里**：烧录 commit 与 `nv-write` 必须用户明确批准，操作级红线在对应子技能（upg / nv）。
5. **产物只落 §4 目录**：日志 / 导出 / 报告不写进技能目录，不散落 `/tmp` 或别的项目。

## 4. 产物与日志落盘（唯一约定）

优先级：`REQ_DIR/logs/` → `PROJECT/logs/` → 会话工作区 `logs/`。

```bash
# REQ_DIR / PROJECT 按 §1 解析后导出；优先用需求目录
LOG_DIR="${REQ_DIR:-$PROJECT}/logs"; mkdir -p "$LOG_DIR"
STAMP=$(date +%Y%m%d-%H%M)
$CTL frames --since 0 --limit 500 > "$LOG_DIR/$STAMP-frames.json"
$CTL logs  --since 0 --limit 200 > "$LOG_DIR/$STAMP-logs.json"
```

- 命名 `YYYYMMDD-HHMM-<kind>-<slug>.json|md`（kind：`frames` / `logs` / `prim` / `upg` / `nv` / `report`）。
- 服务自有的 `service_frames.jsonl`、`audit.jsonl` 是**只读源**（实际路径看 `status.logfile`）；要长期留存就导出到 `REQ_DIR/logs/`，不要把它们当工作区。
- 结论与评审写 `REQ_DIR/DONE.md` 或 `REQ_DIR/logs/<stamp>-report.md`，不要另建散落目录。

## 5. 最小速查

```bash
$CTL status
$CTL version
$CTL prim --limit 20
$CTL frames --limit 20
$CTL topo
```

升级与 NV 操作不要凭记忆：操作步骤在 `hs-dw31-upg` / `hs-dw31-nv`，判据细节读 `$BASE/references/contract.md`。

**烧录不要自己分步**：一条命令出结果 JSON（工程路径 + 包文件即可，回连后自动同步 prim XML）：

```bash
python3 <skill 根>/hs-dw31-upg/scripts/flash.py --project <工程根> --file <包文件>
```

**日志打不出来不要重查**：`hs-dw31-diag` → `references/logs.md` **§8** 已有定因（`0x5310` 模块开关）。
**在 `Application/` 层新写日志要中文注释**：同 §8.4.1（XML 不会自动出条目，按 id 公式手补 `mss_prim_db.xml`）。

## 6. 本技能内的文档（唯一来源）

- `references/contract.md`：服务端点、错误码、烧录门禁与状态机、`0x3410` 布局、成功判据、字段字典、禁止项、8766 控制面。
- `references/errors.md`：端口 / 后端 / 错误码排障。
- `references/events.md` / `references/mcp.md`：SSE 与 MCP（**暂未接入**，标"暂空"= 不要臆造命令）。
- 其余 `references/*.md` 分散在各子技能，按任务分工，互不重复。

维护规则：

- 契约有变化 → 先改 `$BASE/references/contract.md`（和对应子技能 reference），**不要**新增"请看 <某个绝对路径> 的文档"这类指针。
- 参考文件之间冲突时以 `contract.md` 为准，并顺手改掉冲突的那一处。
- 技能外的 `docs/`（若手边有 FC 服务仓库）只作历史背景；冲突以本系列技能为准，并把差异补回 `contract.md`。
