---
name: hs-dw31
description: 什么时候用我：只要确认是【海思 DW31 / 海思 PLC CCO/STA 工程】（模块 DW31/DW31C、版本串 DW31_V100R001C00SPCxxx、plc-project 的 build.sh/CMake 工程），且要做调试类任务——编译出升级包/在线升级烧录、抓日志看帧取证、NV 读写、原始诊断排障、或分析该工程的升级链路/构建/NV/日志——就加载我。我是元技能：只做工程门禁与任务路由，不装操作内容；单域任务按路由表加载一个 hs-dw31-* 子技能。非海思工程、其他厂商芯片、工作台 8790 与 wb-* 系列、工装 645/376.2、CCO/STA 固件 make 打包不要用我。
argument-hint: "[任务：烧录升级 / 抓日志 / 读NV / 看拓扑 / 排障 / 工程分析]"
metadata:
  author: reasonix
  version: 3.0.0
  applies-to: 海思 DW31 / 海思 PLC CCO/STA 工程（模块 DW31C；Windows FC 服务 8765）；不绑定绝对工作区
  source: 2026-11-12 接入；2026-11-17 重构为任务驱动；2026-11-18 由单技能拆分为总分总五技能：本技能退化为纯路由元技能，操作内容下沉到 hs-dw31-base / upg / diag / nv
---

# 海思 DW31 调试路由（hs-dw31）

> 一句话：本技能是 hs-dw31 系列的**元技能**——只做「是不是海思工程」的门禁和「这个任务归谁」的路由；操作步骤全部在子技能里。

## 0. 工程门禁（按「工程 + 任务」判，不按路径判）

工程信号命中任一、任务命中任一，才进入路由：

| 工程信号（任一） | 任务（任一） |
|---|---|
| 用户说海思 DW31 / 海思 PLC CCO/STA | 抓日志、看帧 / prim / 事件，做取证与判读 |
| 模块版本串含 `DW31_V100R001C00SPCxxx`，芯片 `DW31C` | 编译出升级包、选包族（`sg_cco` / `sg_fusion_cco` / `sg_sta`） |
| 工程含 `scripts/build.sh` + `build/config/DW31v100/` | 在线升级 / 烧录（prepare → commit）、进度判定、整包救援 |
| 设备挂在 Windows FC 服务 8765 上（`doctor` 能通） | NV 读写解码、拓扑、原始诊断命令 |
| 用户给出 `.hupg` / `.fwpkg`，或问"这个包能不能烧" | 分析该工程：升级链路、构建体系、NV、日志口径 |

**不要用（任一命中即拒绝）**：

- 非海思工程（其他芯片 / 厂商 / 项目）——即使命令看起来一样。
- HPLC 工作台 8790 / `wb-serial` / `wb-simcon` / 模拟电表——走 `ai-control-plane` 或对应 `wb-*`。
- 只解析 645 / 1376.2 报文、不碰 DW31 设备——走 `wb-appframe` / `knowledge-lookup`。
- 其他项目固件的 `make cco / sta_venus2m*` 打包——走 `firmware-version-build`。
- ECU 698 管理通道——走 `ecu698`。

## 1. 路由表（总 → 分）

| 任务 | 加载 |
|---|---|
| 编译出包、选包族、在线升级 / 烧录、进度与激活判定、救援 | `hs-dw31-base` + `hs-dw31-upg` |
| 抓日志、导出帧、prim / 事件取证、拓扑、原始诊断命令判读 | `hs-dw31-base` + `hs-dw31-diag` |
| NV 读 / 写 / 解码、NV 排障（写了不生效等） | `hs-dw31-base` + `hs-dw31-nv` |
| 跑 CLI、查服务端点 / 错误码 / 判据 / 8766 控制面 | `hs-dw31-base` |
| MCP / SSE（暂未接入） | `hs-dw31-base` 的 `references/mcp.md` / `events.md` |

路由规则：

- **先 base 后子技能**：`hs-dw31-base` 是必读前置（CLI、契约、doctor、落盘约定都在那里）。
- 单域任务只加载一个子技能；跨任务（如"升级完顺便抓日志"）按序逐段加载，不要一次全量。
- 子技能之间**不互相加载**；要换任务回到本表重新路由（分 → 总）。

## 2. 门禁级红线（操作级红线在各子技能内）

1. 只用于海思工程；非海思不操作设备。
2. 烧录 commit、`nv-write` 等高危写操作：授权在对话里，用户明确批准才执行——细则在 `hs-dw31-upg` / `hs-dw31-nv`。
3. 所有结论可追溯（帧 `id` / `ts` / `param_hex` 或 `nv_id` / `rc`），产物只落 `hs-dw31-base` §4 约定目录。

## 3. 工程分析类任务（不操作设备）

要分析升级链路 / 构建体系 / NV / 日志口径但不碰设备时：加载 `hs-dw31-base` 拿路径解析与契约入口，再按主题读对应子技能的 reference（build → upg、logs/topology → diag、nv → nv），全程只读。
