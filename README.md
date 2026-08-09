# Skills

**wyentrepot 的个人技能仓库** — 统一管理所有 AI 助手（Kilo / Reasonix / Claude Code 等）的 skills。

## 目录结构

```
skills/
├── shared/          # 所有环境共用的技能（Kilo + Reasonix 都加载）
├── kilo/            # 仅 Kilo (WSL) 使用的技能，嵌入式开发相关
├── reasonix/        # 仅 Reasonix (Windows) 使用的技能
├── scripts/         # 安装辅助脚本
│   ├── install-kilo.sh        # WSL 下将技能链接到 ~/.kilo/skills
│   └── install-reasonix.sh    # Win 下将技能注册到 ~/.reasonix/config.toml
└── README.md
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

## 技能列表

### Kilo 技能（`kilo/`）

| 名称 | 说明 |
|------|------|
| `cco-coding-standards` | CCO/STA 嵌入式 C/C++ 编码规范（142 条规则） |
| `splc-flash-loop` | 固件编译→烧录→验证闭环 |
| `sta-version-build` | STA 固件大小版本自动编译打包 |
| `sta-version-diff` | 版本差异分析文档生成 |
| `sta-test-build` | STA Unity 单元测试模式编译打包 |

### Reasonix 技能（`reasonix/`）

> 暂无，待添加。

### 共享技能（`shared/`）

> 暂无，待添加。如果某个技能同时适用于 Kilo 和 Reasonix，请放在此目录。

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

- **所有环境共用** → `shared/<技能名>/SKILL.md`
- **仅 Kilo (WSL)** → `kilo/<技能名>/SKILL.md`
- **仅 Reasonix (Win)** → `reasonix/<技能名>/SKILL.md`

提交后，各环境重新运行对应的安装脚本即可生效。
