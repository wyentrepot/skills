# deprecated — 已停用技能（仅供追溯）

> 建库：2026-11-17。本目录下的技能**不参与任何 harness 的默认技能目录**，不会被自动发现或加载。
> 保留文件只为追溯历史实现与证据口径；正常任务请走 `shared/` 下的现行技能。

## 停用清单

| 原路径 | 现路径 | 原属环境 | 停用原因 |
|---|---|---|---|
| `codex/splc-flash-loop/` | `deprecated/codex/splc-flash-loop/` | Codex | EDBG 闭环旧烧录链（WSL → PowerShell → Windows Python → COM），与现行「工作台 8790 + 串口桥」烧录链并行且重复；`wb-flash` 已覆盖烧录与成败判定 |
| `codex/splc-sync-feature/` | `deprecated/codex/splc-sync-feature/` | Codex | 上位机 Windows PyInstaller 打包与双仓特性同步，属已停用的交付流程 |
| `kilo/splc-flash-loop/` | `deprecated/kilo/splc-flash-loop/` | Kilo | 同上（Kilo 版是精简副本，行数约为 Codex 版一半，且早已分叉） |

## 软链处理

| 位置 | 处理 |
|---|---|
| `~/.agents/skills/splc-flash-loop`、`~/.agents/skills/splc-sync-feature` | **已删除**（该根会被 DSH 扫描，留着会把停用技能重新带进模型可见目录） |
| `~/.kilo/skills/splc-flash-loop` | **已重指**到 `deprecated/kilo/splc-flash-loop`（避免悬空软链；Kilo 若也不再使用，删掉这条即可） |
| `~/.codex/skills/splc-flash-loop`、`~/.codex/skills/splc-sync-feature` | **未动**：它们指向 `/root/.cc-switch/skills/` 下的独立快照副本（2026-10-08），与仓库目录无关，本次移动不影响 Codex。若要一并停用，需另行处理 cc-switch 副本 |

## 恢复方式

```bash
cd /home/02-skill-fc/skills
git mv deprecated/codex/splc-flash-loop codex/splc-flash-loop
git mv deprecated/codex/splc-sync-feature codex/splc-sync-feature
git mv deprecated/kilo/splc-flash-loop kilo/splc-flash-loop
# 重建软链（示例）
ln -sfn /home/02-skill-fc/skills/codex/splc-flash-loop ~/.agents/skills/splc-flash-loop
```

## 相关口径

- 现行烧录：`shared/hardware-in-the-loop/wb-flash/`（任务面）+ `wb-serial/`（串口桥 preflight）+ `wb-base/`（接入与授权）。
- 现行串口模型：Windows `serial_bridge.py` ↔ TCP ↔ WSL PTY，已不依赖 usbipd（2026-10-22 起）。
- 历史决策记录见 `reqs/0001-shared-skill-taxonomy/`（当时明确"不移动"这三个技能，本次变动是其后的口径更新）。
