# DONE.md — 0006 技能孤本救援与技能存储收敛（最新在上）

## 2026-11-23 完成

**提交**：`dd0c31f` feat(skills): 7 个孤本技能入仓 + DLP 误报说明 + 清理死链（41 文件，+16216/-3）

### 交付结果

| 项 | 结果 |
|---|---|
| 7 个孤本入仓 | ✅ 逐文件 md5 与原位置一致（提交后从 `git ls-tree` 复核 35 个文件全在） |
| 原位改软链 | ✅ `~/.dsh/skills` ×2、`~/.kilo/skills` ×4 全部指向主仓 |
| 死链清理 | ✅ 本工作区 `.agents/skills` 两个指向 `deprecated/` 的死链已删 |
| DLP 文档 | ✅ README 补"E-SafeNet 导致 git 误报修改"的实测说明、判别命令与禁止事项 |
| README 技能表 | ✅ 补齐 7 项，并补上一直缺失的 `shared/knowledge-base` 小节 |
| 技能数 | 主仓 58 → 65 |

### 关键证据

- **加载零回归**：DSH 技能目录改造前后完全一致——52 个，零增零减，分组/提供者无变化。
- **无死链**：`~/.dsh/skills`、`~/.agents/skills`、`~/.kilo/skills` 三处均 0 个死链；全仓 `find -type l ! -exec test -e` 无输出。
- **内容零改动**：7 个技能 35 个文件逐对 md5 与源一致（含提交后对 git 对象的复核）。

### 遗留说明

- `clang-format` 入仓前就未挂载到任何 harness（仅存在于 D 盘备份），本次**未改变其挂载状态**，仅消除丢失风险；如需启用，加一条软链即可。
- 仓库内另有 31 条**上次会话遗留**的未提交改动（hs-dw31、wb-* 等，属需求 0005），本次未触碰。
- 已判定不救援并保持原样：`parasoft-scan`、`分钟采集数据分析`、`sta-test-build`、`sta-version-build`（均已被主仓技能取代）。
- Windows 侧 `.skills-source` 克隆（`codex/windows-agents-sync`，落后 37 个提交）与 `~/.cc-switch` 快照未处理，用户本次未纳入范围。
