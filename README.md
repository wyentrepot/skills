# Skills

**wyentrepot 的个人技能仓库** — 统一管理所有 AI 助手（Kilo / Reasonix / DeepSeek Harness / Claude Code 等）的 skills。

## 目录结构

```
skills/
├── shared/          # 所有环境共用的技能，按能力域分组
│   ├── development-process/              # 需求、设计与实施计划
│   ├── code-quality/                     # 测试与编码规范
│   ├── hardware-in-the-loop/             # 实机控制、烧录和构建闭环
│   └── research-and-technical-expression/ # 架构与技术表达
├── codex/           # 仅 Codex 使用的专属技能
├── kilo/            # 仅 Kilo (WSL) 使用的技能，嵌入式开发相关
├── reasonix/        # 仅 Reasonix (Windows) 使用的技能
├── dsh/             # 仅 DeepSeek Harness (DSH) 使用的技能（superpowers-dsh 移植包）
├── scripts/         # 工具级安装脚本（不属于任何技能）
│   ├── install-kilo.sh        # WSL 下将技能链接到 ~/.kilo/skills
│   ├── install-reasonix.sh    # Win 下将技能注册到 ~/.reasonix/config.toml
│   └── install-dsh.sh         # 将 dsh/ + shared/ 技能复制到 $DSH_HOME/skills（DSH 用户技能根）
└── README.md
```

**每个技能都是自包含的独立文件夹**。凡是某个技能依赖的脚本，一律放进该技能自己的文件夹内，不散落在仓库根部：

```
shared/<能力域>/<技能名>/
├── SKILL.md            # 技能说明（入口）
├── scripts/            # 该技能自身依赖的脚本
│   ├── xxx.sh
│   └── xxx.py
└── (其他辅助文件)
```

## 环境安装

### 公司办公 — WSL (Kilo)

```bash
# 1. 在 WSL 中 clone 仓库
git clone git@github.com:wyentrepot/skills.git ~/skills

# 2. 运行安装脚本（将 shared/ + kilo/ 的技能链接到 ~/.kilo/skills）
bash ~/skills/scripts/install-kilo.sh

# 3. 重启 Kilo，技能自动加载
```

### 公司办公 — Windows (Reasonix)

```bash
# 1. 在 Git Bash 中 clone 仓库
git clone git@github.com:wyentrepot/skills.git C:/path/to/skills

# 2. 运行安装脚本（将 shared/ + reasonix/ 注册到 reasonix 配置）
bash C:/path/to/skills/scripts/install-reasonix.sh

# 或手动编辑 ~/.reasonix/config.toml，添加：
# [skills]
# paths = ["C:/path/to/skills/shared", "C:/path/to/skills/reasonix"]

# 3. 重启 Reasonix
```

### 个人办公 — Windows (Reasonix)

同上，skills 仓库 clone 到个人电脑，运行 `install-reasonix.sh` 即可。

### 个人办公 — Windows (DeepSeek Harness)

同上，skills 仓库 clone 到个人电脑，运行 `scripts/install-dsh.sh` 即可（将 `dsh/` 下的 superpowers-dsh 技能与 `shared/` 下的共用技能复制到 `$DSH_HOME/skills`，DSH 下一会话自动加载）。

> DSH 技能发现根：用户 `<DSH_HOME>/skills`、项目 `<项目根>/.dsh/skills`。若不用脚本，也可手动把 `dsh/*` 与 `shared/*` 复制到 `<DSH_HOME>/skills/`。注意：公司 DLP 环境下请用 WSL 或 DSH 自身进程写入，避免把 git checkout 到 NTFS 后被 E-SafeNet 透明加密，导致 DSH 无法读取。

## 技能列表

### Kilo 技能（`kilo/`）

| 名称 | 说明 |
|------|------|
| `cco-coding-standards` | CCO/STA 嵌入式 C/C++ 编码规范（142 条规则） |
| `cco-loghooks-scan` | CCO 固件日志打印扫描 → 结构化清单，供 loghooks 规则作数据源（只读采集不改码） |
| `observe-workbench-logs` | ZZT_SELF 工作台日志/帧的硬件非侵入、有界 AI 取证 |
| `splc-flash-loop` | 固件编译→烧录→验证闭环 |
| `sta-version-diff` | 版本差异分析文档生成 |
| `sta-test-build` | STA Unity 单元测试模式编译打包 |

### Reasonix 技能（`reasonix/`）

> Superpowers 软件工程方法论（由 obra/superpowers 移植到 Reasonix，MIT 许可）。

| 名称 | 说明 |
|------|------|
| `superpowers-brainstorming` | 构思功能/新点子 → 先出批准的设计再写代码 |
| `superpowers-writing-plans` | 多步骤任务先写计划 |
| `superpowers-executing-plans` | 带检查点逐步执行计划 |
| `superpowers-test-driven-development` | 写代码前先写失败测试（RED-GREEN-REFACTOR） |
| `superpowers-systematic-debugging` | 遇到 bug/测试失败，从证据出发调查 |
| `superpowers-verification-before-completion` | 说"完成/修复/通过"前先出示证据 |
| `superpowers-finishing-a-development-branch` | 分支收尾：merge / PR / 清理 |
| `superpowers-receiving-code-review` | 收到 review 反馈后逐条核验 |
| `superpowers-using-git-worktrees` | 需要隔离工作空间时 |
| `superpowers-writing-skills` | 编写/测试 Reasonix skill |
| `superpowers-sync-upstream` | 同步上游 obra/superpowers 更新 |
| `opencode-mcp` | Reasonix → OpenCode MCP 桥：把编码/探索/审查任务委托给 WSL 内 OpenCode 的 zen-* agent 执行（含可用模型与派发规则，详见 docs/opencode-mcp-reasonix.md） |


### DSH 技能（`dsh/`）

> superpowers-dsh 软件工程方法论（由 obra/superpowers 移植到 DeepSeek Harness，移植源 [LayneChai/superpowers-dsh](https://github.com/LayneChai/superpowers-dsh)，MIT 许可）。

| 名称 | 说明 |
|------|------|
| `using-superpowers` | 入口技能：如何查找与使用技能 |
| `brainstorming` | 构思功能/新点子 → 先出批准的设计再写代码 |
| `writing-plans` | 多步骤任务先写计划 |
| `executing-plans` | 带检查点逐步执行计划 |
| `subagent-driven-development` | 每任务派发全新子代理并评审 |
| `dispatching-parallel-agents` | 独立工作扇出到并行代理 |
| `systematic-debugging` | 遇到 bug/测试失败，从证据出发调查 |
| `test-driven-development` | 写代码前先写失败测试（RED-GREEN-REFACTOR） |
| `verification-before-completion` | 说"完成/修复/通过"前先出示证据 |
| `requesting-code-review` | 合并前获得严格评审 |
| `receiving-code-review` | 收到 review 反馈后逐条核验 |
| `finishing-a-development-branch` | 分支收尾：merge / PR / 清理 |
| `using-git-worktrees` | 需要隔离工作空间时 |
| `writing-skills` | 编写/测试 DSH skill |

### 共享技能（shared/）

#### 研发流程（`shared/development-process/`）

| 名称 | 说明 |
|------|------|
| `brainstorming` | 需求存在关键设计选择时，先形成获批设计。 |
| `req-mgmt` | 需求/进度管理：需求变更 ADR 只追加、多需求切换，且多步计划由 `writing-plans` 生成。 |
| `writing-plans` | 已批准的多步骤任务在改动前形成可执行、可验证的实施计划。 |

#### 代码质量（`shared/code-quality/`）

| 名称 | 说明 |
|------|------|
| `test-driven-development` | 行为变更先做失败前置检查，再最小实现和回归验证。 |
| `coding-standards` | 嵌入式 C 代码的最小改动、资源清理和可移植性规范。 |

#### 实机闭环（`shared/hardware-in-the-loop/`）

| 名称 | 说明 |
|------|------|
| `ai-control-plane` | 通过 HTTP 驱动真机 HPLC 工作台，覆盖串口、烧录、日志和证据。 |
| `sta-version-build` | STA 固件大小版本的三组变体编译、打包和归档。 |

#### 研究与技术表达（`shared/research-and-technical-expression/`）

| 名称 | 说明 |
|------|------|
| `archify` | 生成可验证的架构、流程、时序、数据流和生命周期图。 |


## 添加新技能

### 格式

所有技能均使用以下格式（与 Kilo 和 Reasonix 兼容）：

```markdown
---
name: <技能名>
description: <一句话描述>
---

# 技能标题

## 使用方式

...
```

### 存放位置

- **所有环境共用** → `shared/<能力域>/<技能名>/SKILL.md`
- **仅 Kilo (WSL)** → `kilo/<技能名>/SKILL.md`
- **仅 Reasonix (Win)** → `reasonix/<技能名>/SKILL.md`

### 技能自身依赖的脚本

若某技能需要脚本才能工作（例如打包、解析、自动生成），把脚本放在该技能文件夹内的 `scripts/` 子目录，与 `SKILL.md` 同级：

```
<技能名>/
├── SKILL.md
└── scripts/
    ├── build.sh
    └── parse.py
```

> **注意**：仓库根 `scripts/` 只放安装/工具级脚本，不要放某个技能专属的脚本。

### 生效方式

提交后，各环境重新运行对应的安装脚本即可生效。若技能文件夹带 `scripts/`，安装脚本仍只链接技能目录本身，技能内的子目录会随技能目录一起生效，无需额外配置。
