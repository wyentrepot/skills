---
name: hs-dw31-upg
description: 什么时候用我：确认是海思 DW31 工程后，要编译出升级包、选包族（sg_cco / sg_fusion_cco / sg_sta）、在线升级烧录（prepare → commit）、看升级进度、解析 0x3410 状态、核对激活（0x3013）、失败救援，或问"这个 .hupg / .fwpkg 包能不能烧"。前置 REQUIRED：先读 hs-dw31-base 拿 $BASE（CLI、契约、doctor、落盘）。仅限海思工程；非海思、工作台 8790 的 wb-flash 烧 iap、其他项目固件 make 打包（firmware-version-build）不要用我。
argument-hint: "[任务：出包 / 烧录 / 升级进度 / 激活判定 / 救援]"
metadata:
  author: reasonix
  version: 3.0.0
  applies-to: 海思 DW31 / 海思 PLC CCO/STA 工程（模块 DW31C；Windows FC 服务 8765）；不绑定绝对工作区
  source: 2026-11-18 由单技能 hs-dw31 拆分而来；承载原 references/upgrade.md、build.md 与烧录级红线
---

# 海思 DW31 升级与烧录（hs-dw31-upg）

> 一句话：出包、烧录、升级判定与救援。**前置 REQUIRED：先读 `hs-dw31-base`**——CLI（`python3 $BASE/scripts/fcctl.py`）、契约（`$BASE/references/contract.md`）、doctor 前置与落盘约定都在那里；本技能只装升级与编译的操作步骤。

## 0. 前置（每次必做）

1. 读 `hs-dw31-base`：拿到 `$BASE`，跑 doctor，按其 §2 判定能否继续。
2. `PROJECT` 解析：编译 / 选包需要；用户已给出包文件时可不解析。

## 1. 加载模型（渐进式，一次任务只读一层）

| 任务 | 只读这一个 |
|---|---|
| prepare / commit / 进度 / `0x3410` / 激活判定 / 回滚 / 救援 | `references/upgrade.md` |
| 编译出包、选包族、产物位置 | `references/build.md` |
| 烧录门禁与状态机、`0x3410` 布局、成功判据、字段字典 | `$BASE/references/contract.md`（§3 / §4） |
| 端口 / 后端 / 错误码排障、8766 控制面 | `$BASE/references/errors.md`、`contract.md` §2 |

规则：

- 一次任务只读一层；正文里 `contract.md §x` 一律指 `$BASE/references/contract.md §x`。
- 参考文件之间冲突时以 `contract.md` 为准，并顺手改掉冲突的那一处。

## 2. 烧录级红线

1. **授权在对话里**：用户明确说"允许 / 可以烧 / 直接升"才 commit；先 prepare 并报 `sha256` / 当前版本 / 目标 MAC；commit 带 `approved_by=cli` + `user_approval`；**禁止** `/api/upg/load`、`/api/upg/start`。
2. **包族要对**：融合终端 / ECU 只烧 `out/sg_fusion_cco/` 的在线包，CCO 只烧 `out/sg_cco/`；两族文件名相同，只能看目录 / 构建目标（烧错族 → `0x8007`）。
3. 包路径必须在服务白名单内（`contract.md` §3.2）；直接 app 升级 `0x3412/0x3415` 的 `file_blk_size` 必须填真实长度，`0x3410` 按真实偏移解析。
4. 升级判定不要凭记忆：读 `references/upgrade.md` + `contract.md` §3–§4；升级完成后必须关闭并重开串口会话再读 `0x3013`。

## 3. 产物

落盘按 `hs-dw31-base` §4：升级过程记录 kind=`upg`，结论写 `REQ_DIR/DONE.md` 或 `<stamp>-report.md`。
