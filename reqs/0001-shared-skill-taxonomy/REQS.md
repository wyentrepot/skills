# REQS.md — 需求基线（需求 ID：0001，标题：共享技能分类迁移）

## 当前生效基线（版本：v1，更新：2026-09-08）

### 目标

将当前 Codex 使用的通用技能归入 `shared/` 的能力域目录，并把 Codex 映射从旧 `codex/` 或旧 `shared/` 位置切换到新目录。

### 需求点

- `brainstorming`、`req-mgmt`、`writing-plans` 归入 `shared/development-process/`。
- `test-driven-development`、`coding-standards` 归入 `shared/code-quality/`。
- 现有 `ai-control-plane`、`sta-version-build` 归入 `shared/hardware-in-the-loop/`；现有 `archify` 归入 `shared/research-and-technical-expression/`。
- 删除上述技能在 `codex/` 的旧目录；不移动 `splc-flash-loop`、`splc-sync-feature`、`wsl-safe-writing`。
- 将 Codex 配置中受影响的技能路径更新为新 `shared/` 目录，并新增 `sta-version-build` 的显式映射。
- 更新共享技能安装脚本和仓库说明，使嵌套分类目录仍能被安装或发现。

### 验收标准

- [ ] 8 个目标技能目录均只存在于预定的 `shared/<能力域>/` 路径，且各自包含完整 `SKILL.md` 与原有资源。
- [ ] Codex 配置的受影响路径均指向存在的 `shared/` 技能目录；旧路径不再启用。
- [ ] Kilo、DSH 安装脚本能递归发现 `shared/` 下的技能目录，并保持同名目标的安全跳过行为。
- [ ] README 反映新的共享技能分类。
- [ ] 迁移校验、各技能校验、脚本语法检查和 `git diff --check` 均通过。

### 关联代码分支（仅记录）

main

## 变更记录（只追加，禁止覆盖）

### 变更 1 ｜ 2026-09-08 ｜ 用户
- **改成什么**: 首次建立共享技能分类迁移基线。
- **为什么**: 将研发流程、代码质量、实机闭环和研究/技术表达类能力集中到 `shared/`，移除 Codex 目录中的重复副本。
- **影响**: 共享技能目录、Codex 本地配置、安装脚本、仓库 README。
- **变更前基线**: 无（初始版本）。
- **变更后基线**: v1。
- **被取代**: 无。
