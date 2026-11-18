---
name: hs-dw31
description: 什么时候用我：只要确认是【海思 DW31 / 海思 PLC CCO/STA 工程】（模块 DW31/DW31C、版本串 DW31_V100R001C00SPCxxx、plc-project 的 build.sh/CMake 工程），且要抓日志或看帧/prim 取证、编译出升级包、在线升级/烧录、NV/拓扑/原始诊断命令排障、或分析该工程的升级链路/构建/NV/日志——就加载我。工程根按会话解析，不绑定固定工作区。非海思工程、其他厂商芯片、工作台 8790 与 wb-* 系列、工装 645/376.2 不要用我。
argument-hint: "[任务：抓日志 / 升级 / 出包 / 读NV / 看拓扑 / 排障 / 工程分析]"
metadata:
  author: reasonix
  version: 2.0.0
  applies-to: 海思 DW31 / 海思 PLC CCO/STA 工程（模块 DW31C；Windows FC 服务 8765）；不绑定绝对工作区
  source: 2026-11-12 接入；2026-11-17 按用户反馈重构：触发改为任务驱动、路径改为会话解析、契约内联到 references/contract.md；2026-11-18 补 8766 控制面（重启 8765 / 让出端口）、宿主侧 DB 同步、`item=null` 与 `relogin` 卡死两个实测坑
---

# 海思 DW31 上位机调试（hs-dw31）

> 一句话：本技能是**海思 DW31 工程的调试上位机**（Windows FC 服务 8765 + 本技能 CLI）。工程路径不写死，契约就在本技能内。

## 0. 何时用 / 不用（按「工程 + 任务」判，不按路径判）

工程信号命中任一、任务命中任一，就加载：

| 工程信号（任一） | 任务（任一） |
|---|---|
| 用户说海思 DW31 / 海思 PLC CCO/STA | 抓日志、看帧 / prim / 事件，做取证与判读 |
| 模块版本串含 `DW31_V100R001C00SPCxxx`，芯片 `DW31C` | 编译出升级包、选包族（`sg_cco` / `sg_fusion_cco` / `sg_sta`） |
| 工程含 `scripts/build.sh` + `build/config/DW31v100/` | 在线升级（prepare → commit）、进度判定、整包救援 |
| 设备挂在 Windows FC 服务 8765 上（`doctor` 能通） | NV 读写解码、拓扑、原始诊断命令 |
| 用户给出 `.hupg` / `.fwpkg`，或问"这个包能不能烧" | 分析该工程：升级链路、构建体系、NV、日志口径 |

**不要用**：

- 非海思工程（其他芯片 / 厂商 / 项目）——即使命令看起来一样。
- HPLC 工作台 8790 / `wb-serial` / `wb-simcon` / 模拟电表——走 `ai-control-plane` 或对应 `wb-*`。
- 只解析 645 / 1376.2 报文、不碰 DW31 设备——走 `wb-appframe` / `knowledge-lookup`。
- 其他项目固件的 `make cco / sta_venus2m*` 打包——走 `firmware-version-build`。

## 1. 目录与路径（唯一规则：运行时解析，禁止写死）

| 名称 | 怎么得到 | 用途 |
|---|---|---|
| `SKILL_DIR` | 加载技能时给出的技能目录（base directory） | `$SKILL_DIR/scripts/fcctl.py`；命令里不要固化仓库绝对路径 |
| `PROJECT` | ① 用户给的路径 → ② `$HS_DW31_PROJECT` → ③ `fcctl status` 的 `prim.path` / `biz.dir` 反推 → ④ 从当前目录向上找 `scripts/build.sh` + `build/config/DW31v100` → ⑤ 仍不唯一就问用户 | 只读工程；编译与产物都在它下面 |
| `SERVICE` | `fcctl status` 的 `logfile` 等字段，或现场 `C:\fc_diag_client` | 服务自有文件（samples / 审计 / 帧日志）；**只读写服务自己的文件，不当工作区** |
| `REQ_DIR` | `PROJECT/reqs/<id>-<slug>/`（或会话工作区的 `reqs/<id>-<slug>/`） | 日志与报告落这里，见 §5 |

```bash
CTL="python3 $SKILL_DIR/scripts/fcctl.py"   # $SKILL_DIR = 加载时给的技能目录
$CTL doctor
```

- 找不到 `PROJECT` 不影响只读取证（状态 / 帧 / 日志都走服务）；只有编译、选包、看工程配置时才需要它。
- **任何情况下都不要假定某个固定工作区路径存在**；也不要因为当前目录"不在某个路径下"就不加载本技能。

## 2. 加载模型（渐进式，一次只读一层）

| 任务 | 只读这一个 |
|---|---|
| 服务/烧录契约、错误码、字段、判据（**唯一权威**） | `references/contract.md` |
| 升级：prepare / commit / 进度 / 0x3410 / 激活判定 / 回滚 | `references/upgrade.md` |
| 抓日志：状态、帧、日志帧、prim 行与结构树 | `references/logs.md` |
| NV 读 / 写 / 解码 | `references/nv.md` |
| 拓扑 | `references/topology.md` |
| 原始诊断命令 | `references/raw.md` |
| 端口 / 后端 / 错误码排障 | `references/errors.md` |
| **重启 8765 / 让出 COM8 / 换宿主 DB**（8766 控制面） | `references/contract.md` §2.1–§2.2 |
| 编译出包、选包族、产物位置 | `references/build.md` |
| MCP / SSE（暂未接入） | `references/mcp.md` / `references/events.md` |

规则：

- 一次任务只读一层；要契约细节就读 `contract.md`，**不要去翻技能外的文档**（见 §7）。
- reference 标"暂空"= 该功能未接入，不要臆造命令。
- 参考文件之间冲突时以 `contract.md` 为准，并顺手改掉冲突的那一处。

## 3. 通用前置

```bash
$CTL doctor
```

- `data.selected=legacy` 且 `data.legacy.device_ready=true` → 继续。
- `device_ready=false` → 只做 `status`，按 `references/errors.md` 处理；不发设备命令。
- `data.selected=null` → 停，让用户启动 Windows 侧 FC 服务；不要猜。

## 4. 红线

1. **只用于海思工程**；非海思不操作设备。
2. **烧录授权在对话里**：用户明确说"允许 / 可以烧 / 直接升"才 commit；先 prepare 并报 `sha256` / 当前版本 / 目标 MAC；commit 带 `approved_by=cli` + `user_approval`；**禁止** `/api/upg/load`、`/api/upg/start`。
3. **包族要对**：融合终端 / ECU 只烧 `out/sg_fusion_cco/` 的在线包，CCO 只烧 `out/sg_cco/`；两族文件名相同，只能看目录 / 构建目标（烧错族 → `0x8007`）。
4. **禁止手工写 NV `0xF05` 当提交**（含自定义 `0x531E`）：flashboot 不认，实测会把板子带进失联，只能 BurnTool 救援。
5. **写操作要用户点名**：`nv-write` 必须 `--confirm`。
6. **先读状态再写**：`start_running=true` 或 `port_open=false` 时停手。
7. **证据可追溯**：结论带帧 `id` / `ts` / `param_hex` 或 `nv_id` / `rc`，不编造解码值。
8. **产物只落 §5 目录**：日志 / 导出 / 报告不写进技能目录，不散落 `/tmp` 或别的项目。

## 5. 产物与日志落盘（唯一约定）

优先级：`REQ_DIR/logs/` → `PROJECT/logs/` → 会话工作区 `logs/`。

```bash
# REQ_DIR / PROJECT 按 §1 解析后导出；优先用需求目录
LOG_DIR="${REQ_DIR:-$PROJECT}/logs"; mkdir -p "$LOG_DIR"
STAMP=$(date +%Y%m%d-%H%M)
$CTL frames --since 0 --limit 500 > "$LOG_DIR/$STAMP-frames.json"
$CTL logs  --since 0 --limit 200 > "$LOG_DIR/$STAMP-logs.json"
```

- 命名 `YYYYMMDD-HHMM-<kind>-<slug>.json|md`（kind：`frames` / `logs` / `prim` / `upg` / `report`）。
- 服务自有的 `service_frames.jsonl`、`audit.jsonl` 是**只读源**（实际路径看 `status.logfile`）；要长期留存就导出到 `REQ_DIR/logs/`，不要把它们当工作区。
- 结论与评审写 `REQ_DIR/DONE.md` 或 `REQ_DIR/logs/<stamp>-report.md`，不要另建散落目录。

## 6. 最小速查

```bash
$CTL status
$CTL version
$CTL prim --limit 20
$CTL frames --limit 20
$CTL nv-read 1025
$CTL topo
```

升级与判定不要凭记忆：读 `references/upgrade.md` + `references/contract.md` §4。

## 7. 本技能内的文档（唯一来源）

- `references/contract.md`：服务端点、错误码、烧录门禁与状态机、`0x3410` 布局、成功判据、字段字典、禁止项。
- 其余 `references/*.md`：按任务分工，互不重复。

维护规则：

- 契约有变化 → 先改 `contract.md`（和对应 reference），**不要**新增"请看 <某个绝对路径> 的文档"这类指针。
- 技能外的 `docs/`（若手边有 FC 服务仓库）只作历史背景；冲突以本技能为准，并把差异补回 `contract.md`。
