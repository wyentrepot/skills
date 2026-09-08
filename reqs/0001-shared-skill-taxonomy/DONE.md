# DONE.md — 完成日志（需求：0001）

> 完成后只追加，最新在上。

## 2026-09-08 — 共享技能分类迁移
- **做了什么**: 将 8 个共享技能按研发流程、代码质量、实机闭环、研究与技术表达归类；更新 Codex 映射、Kilo/DSH 安装脚本和 README。
- **为什么**: 移除 Codex 中的通用技能重复副本，使跨环境共享技能按能力域组织。
- **涉及文件**: `shared/`、`codex/`、`scripts/install-kilo.sh`、`scripts/install-dsh.sh`、`README.md`、`/mnt/c/Users/A24006872/.codex/config.toml`。
- **执行计划**: PLAN.md（依据基线 v1）
- **验证**: 新旧路径、配置引用、req-mgmt 契约、技能校验、脚本语法和 `git diff --check` 均通过；`ai-control-plane` 的通用校验因既有 `argument-hint` frontmatter 不兼容而未纳入通过项。
