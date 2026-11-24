---
name: hs-dw31-upg
description: 什么时候用我：确认是海思 DW31 工程后，要在线升级烧录、看升级结果/激活、或编译出升级包。**烧录只有一条命令**：给工程路径 + 包文件 → 跑 `scripts/flash.py` → 直接拿结果 JSON（prepare/commit/进度/回连/prim XML 同步/激活核对全在里面，AI 不要自己拆步骤）。前置 REQUIRED：先读 hs-dw31-base 拿 $BASE。仅限海思工程；非海思、工作台 8790 的 wb-flash 烧 iap、其他项目固件 make 打包（firmware-version-build）不要用我。
argument-hint: "[工程路径] [包文件]"
metadata:
  author: reasonix
  version: 4.0.0
  applies-to: 海思 DW31 / 海思 PLC CCO/STA 工程（模块 DW31C；Windows FC 服务 8765）
  source: 2026-11-18 收口为脚本化单入口（scripts/flash.py），取消多步 prepare/commit 手工流程
---

# 海思 DW31 升级与烧录（hs-dw31-upg）

> 一句话：**一条命令升级，直接拿 JSON。** 前置 REQUIRED：先读 `hs-dw31-base`。

## 1 烧录：唯一入口（不要拆步骤）

AI 只做三件事：**① 拿工程路径 ② 拿包文件 ③ 跑脚本读 JSON。**

```bash
python3 <skill 根>/hs-dw31-upg/scripts/flash.py \
  --project "$PROJECT" \
  --file out/sg_fusion_cco/bin/DW31v100_mcore_sg_cco_upg.bin
```

- `--file` 可以是相对 `--project` 的路径，也可以是绝对路径（给了绝对路径连 `--project` 都可省）。
- 脚本内部依次完成：`doctor` → `flash-prepare` → `flash-commit` → 轮询进度 → 等模块复位回连 → **自动同步宿主 prim XML** → `0x3013` 激活核对。
- **stdout 只有一份 JSON**；退出码 `0` = 烧成功且已回连。失败时 JSON 带 `ok:false`、`step`、`failed_at`、`error`。
- 关键字段：`flash.state/percent/blocks/rcv_file_size/upg_status_text/error_code`、`after.reconnect_seconds`、`prim.synced/count`、`activation`。

可选（默认都对，正常不用给）：

| 参数 | 用途 |
|---|---|
| `--dry-run` | 只 prepare 不烧，先看 sha256 / 当前版本 / 目标 MAC |
| `--xml none\|<路径>` | 默认 auto：从工程构建产物找 `mss_prim_db.xml` 并热加载 |
| `--json-out 文件` | 结果另存一份 |
| `--timeout 秒` | 烧录轮询上限，默认 300 |

**红线**：用户明确说"可以烧/直接升"才允许运行本脚本；不要自己拆成 prepare + commit 两步手工调。

## 2 出包（要改代码时才用）

| 任务 | 只读这一个 |
|---|---|
| 编译出包、选包族（`sg_cco` / `sg_fusion_cco` / `sg_sta`）、产物位置 | `references/build.md` |

包族必须对：融合终端 / ECU 只烧 `out/sg_fusion_cco/`，国网 CCO 只烧 `out/sg_cco/`；文件名相同，只能看目录（烧错族 → `0x8007`）。

## 3 出问题时才读

| 现象 | 读 |
|---|---|
| 判据 / `0x3410` 布局 / 状态机 / 救援 | `references/upgrade.md` + `$BASE/references/contract.md` §3–§4 |
| 端口占用 / 后端不可达 / 错误码 | `$BASE/references/errors.md`、`contract.md` §2 |
| 烧完日志看不见 | `hs-dw31-diag` → `references/logs.md` §8 |

## 4 产物

`--json-out` 落到 `REQ_DIR/logs/<stamp>-upg.json`；结论写 `REQ_DIR/DONE.md` 或 `<stamp>-report.md`。
