---
name: hs-dw31-nv
description: 什么时候用我：确认是海思 DW31 工程后，要 NV 读 / 写 / 解码、按 id 查 NV 值，或排障"NV 写了不生效 / prim/reload 不重载 NV 目录 / 需要重启诊断服务才能加载"。前置 REQUIRED：先读 hs-dw31-base 拿 $BASE（CLI、契约、doctor、落盘）。仅限海思工程；非海思、8790 工作台的 NV 相关操作（走 wb-* 系列）不要用我。
argument-hint: "[任务：nv-read / nv-write / NV解码 / NV排障]"
metadata:
  author: reasonix
  version: 3.0.0
  applies-to: 海思 DW31 / 海思 PLC CCO/STA 工程（模块 DW31C；Windows FC 服务 8765）；不绑定绝对工作区
  source: 2026-11-18 由单技能 hs-dw31 拆分而来；承载原 references/nv.md 与 NV 写红线（0xF05 / --confirm）
---

# 海思 DW31 NV 读写（hs-dw31-nv）

> 一句话：NV 读、写、解码与 NV 排障。**前置 REQUIRED：先读 `hs-dw31-base`**——CLI（`python3 $BASE/scripts/fcctl.py`）、契约（`$BASE/references/contract.md`）、doctor 前置与落盘约定都在那里；本技能只装 NV 操作步骤与写红线。

## 0. 前置（每次必做）

1. 读 `hs-dw31-base`：拿到 `$BASE`，跑 doctor，按其 §2 判定能否继续。
2. **先读状态再写**：`start_running=true` 或 `port_open=false` 时停手。

## 1. 加载模型（渐进式，一次任务只读一层）

| 任务 | 只读这一个 |
|---|---|
| NV 读 / 写 / 解码、命令参数 | `references/nv.md` |
| NV 字段字典、判据、禁止项 | `$BASE/references/contract.md` |
| 端口 / 后端 / 错误码排障 | `$BASE/references/errors.md` |

规则：

- 一次任务只读一层；正文里 `contract.md §x` 一律指 `$BASE/references/contract.md §x`。
- 参考文件之间冲突时以 `contract.md` 为准，并顺手改掉冲突的那一处。

## 2. NV 写红线

1. **禁止手工写 NV `0xF05` 当提交**（含自定义 `0x531E`）：flashboot 不认，实测会把板子带进失联，只能 BurnTool 救援。
2. **写操作要用户点名**：`nv-write` 必须 `--confirm`；用户没明确批准不写。
3. **写前先读**：同名 NV 先 `nv-read` 记录原值（`nv_id` / 原值 / `rc` 可追溯），再写。
4. **NV 目录重载坑**：`/api/prim/reload` **不重载 NV 目录**——写完要生效必须重启诊断服务：8766 控制面 `diag/stop` → `diag/start`（见 `nv.md`、`contract.md` §2.1）。

## 3. 产物

落盘按 `hs-dw31-base` §4：NV 操作记录 kind=`nv`，结论写 `REQ_DIR/DONE.md` 或 `<stamp>-report.md`。
