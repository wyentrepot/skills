---
name: hs-dw31-diag
description: 什么时候用我：确认是海思 DW31 工程后，要抓日志、导出帧、看 prim 行与结构树、事件取证、查拓扑、跑原始诊断命令并判读，或把服务自有帧日志导出留档。前置 REQUIRED：先读 hs-dw31-base 拿 $BASE（CLI、契约、doctor、落盘）。仅限海思工程；非海思、只解析 645/1376.2 报文不碰设备（走 wb-appframe）、8790 链路侦听（走 wb-listener）、模拟集中器/电表（走 wb-simcon/wb-simeter）不要用我。
argument-hint: "[任务：抓日志 / 看帧 / prim / 拓扑 / 原始诊断]"
metadata:
  author: reasonix
  version: 3.0.0
  applies-to: 海思 DW31 / 海思 PLC CCO/STA 工程（模块 DW31C；Windows FC 服务 8765）；不绑定绝对工作区
  source: 2026-11-18 由单技能 hs-dw31 拆分而来；承载原 references/logs.md、raw.md、topology.md 与证据红线
---

# 海思 DW31 观测与取证（hs-dw31-diag）

> 一句话：抓日志、看帧 / prim / 事件、拓扑、原始诊断命令的取证与判读。**前置 REQUIRED：先读 `hs-dw31-base`**——CLI（`python3 $BASE/scripts/fcctl.py`）、契约（`$BASE/references/contract.md`）、doctor 前置与落盘约定都在那里；本技能只装观测类操作步骤。

## 0. 前置（每次必做）

1. 读 `hs-dw31-base`：拿到 `$BASE`，跑 doctor，按其 §2 判定能否继续。
2. 观测类任务是只读的，`PROJECT` 解析不出来也能继续（状态 / 帧 / 日志都走服务）。

## 1. 加载模型（渐进式，一次任务只读一层）

| 任务 | 只读这一个 |
|---|---|
| 抓日志：状态、帧、日志帧、prim 行与结构树 | `references/logs.md` |
| 原始诊断命令 | `references/raw.md` |
| 拓扑 | `references/topology.md` |
| 服务端点、字段判据、错误码、8766 控制面 | `$BASE/references/contract.md`、`$BASE/references/errors.md` |

规则：

- 一次任务只读一层；正文里 `contract.md §x` 一律指 `$BASE/references/contract.md §x`。
- reference 标"暂空"= 该功能未接入，不要臆造命令。
- 参考文件之间冲突时以 `contract.md` 为准，并顺手改掉冲突的那一处。

## 2. 取证级红线

1. **证据可追溯**：结论必须带帧 `id` / `ts` / `param_hex` 或 `prim` 行号，不编造解码值；解析不了就明说"未解析"，不要猜。
2. **只读不写**：本技能不包含任何写设备操作；要写 NV 去 `hs-dw31-nv`，要烧录去 `hs-dw31-upg`。
3. 服务自有 `service_frames.jsonl`、`audit.jsonl` 是只读源；长期留存按 `hs-dw31-base` §4 导出到 `REQ_DIR/logs/`。

## 3. 产物

落盘按 `hs-dw31-base` §4：kind=`frames` / `logs` / `prim`，结论写 `REQ_DIR/DONE.md` 或 `<stamp>-report.md`。
