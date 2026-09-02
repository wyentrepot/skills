# DSH Skills（DeepSeek Harness）

此目录存放仅 **DeepSeek Harness (DSH)** 使用的技能——`superpowers-dsh` 技能包，
由 [obra/superpowers](https://github.com/obra/superpowers)（MIT，© Jesse Vincent
及贡献者）移植到 DSH，移植源：
[github.com/LayneChai/superpowers-dsh](https://github.com/LayneChai/superpowers-dsh)（MIT）。

DSH 的技能发现规则（`@deepseek-ai/dsh-skill-filesystem`）：

- 技能格式：`<技能名>/SKILL.md`（或平铺 `<技能名>.md`），YAML frontmatter 必含
  `name`（kebab-case）与 `description`，可选 `whenToUse`。
- 发现根（按 rank）：项目 `<项目根>/.dsh/skills`、`<项目根>/.agents/skills`、
  用户 `<DSH_HOME>/skills`（Windows 桌面版默认
  `C:\Users\<user>\AppData\Roaming\dsh-desktop\harness\skills`）、`~/.agents/skills`。
- 本目录**不**会被 DSH 直接扫描，需通过 `scripts/install-dsh.sh` 安装到
  `<DSH_HOME>/skills` 后生效（DSH 会实时监视该目录）。

## 技能列表（14 个）

| 技能 | 用途 |
| --- | --- |
| `using-superpowers` | 如何查找和使用技能；入口技能 |
| `brainstorming` | 通过协作对话把想法变成设计 |
| `writing-plans` | 根据规格编写全面的实施计划 |
| `executing-plans` | 按书面计划执行，带评审检查点 |
| `subagent-driven-development` | 每个任务派发全新子代理并评审 |
| `dispatching-parallel-agents` | 把独立工作扇出到并行代理 |
| `systematic-debugging` | 先找根因的调试纪律 |
| `test-driven-development` | RED-GREEN-REFACTOR 实施循环 |
| `verification-before-completion` | 声称成功前先拿出证据 |
| `requesting-code-review` | 合并前获得严格评审 |
| `receiving-code-review` | 核实反馈，而不是盲目照做 |
| `finishing-a-development-branch` | 安全地整合已完成的工作 |
| `using-git-worktrees` | 功能开发的隔离工作区 |
| `writing-skills` | 以 TDD 方式编写并验证新技能 |

## DSH 工具映射

`using-superpowers` 技能内含 `references/dsh-tools.md`——完整的
Claude-Code → DSH 工具映射（`pwsh`、`subagent`/`subagent_fork`、
`workflow`、`goal`、`skill` 等）。

## 与上游的差异（DSH 移植说明）

- 去掉了命名空间前缀：`superpowers:brainstorming` → `brainstorming`。
- 子代理引用映射到 DSH 的 `subagent` / `subagent_fork` 工具。
- `brainstorming` 的视觉伴侣包含 Windows 说明：Node 服务
  （`scripts/server.cjs`）全平台可跑；`.sh` 辅助脚本仅限 bash。

## 许可证

MIT。技能内容改编自 obra/superpowers（MIT）。