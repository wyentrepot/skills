# 🏢 公司环境 — Reasonix 配置参考

> 对应环境：WSL + Windows 双环境

## 可能涉及的配置项

```toml
# 公司环境 reasonix.toml 示例（草稿）
[agent]
reasoning_language = "zh-CN"

# Provider 配置（按实际使用的模型填写）
# [provider.deepseek]
# api_key_env = "DEEPSEEK_API_KEY"
# model = "deepseek-chat"

# 工作区常驻指令
# 涉及 WSL + Win 双环境时，可在 AGENTS.md 中说明
```

## 领域常量参考

> 以下常量对应公司环境实际值，详见 [company-office.md](../company-office.md)。

| 常量 | 值 / 说明 |
|------|------|
| WSL 发行版 | Ubuntu 22.04.5 LTS（WSL2） |
| Linux 工作根目录 | `/home`（STA: `/home/H_STA/04/sta`；CCO: `/home/H_CCO/001/cco`） |
| SPLC 闭环工具 | `/home/kilo/edbg_pc_debug_tool_full_source`（`python3 -m edbg_pc.cli loop ...`） |
| 证据目录 | `/d/sta/<project>/`、`/d/cco/<project>/` |
| 编码规范 | `/home/rule/project-index/cco/coding-standards.mdc` |
| Windows 工作根目录 | `D:\`（WSL 挂载 `/mnt/d`） |
| COM 口 / 硬件路径 | 串口按次枚举 + 用户确认（CH341/CP210x），不写死 |
| 固件路径 | `/home/H_STA/04/sta/firmware/`、`/home/H_CCO/001/cco/firmware/` |
| 代理配置 | 按实际填写（如有） |

## 备注

- 串口端口每次现场枚举 + 用户确认，不信任历史 readme 的 port 字段直接烧录
- 具体常量值优先记录在 `company-office.md`，避免与流程混淆（遵循跨会话知识分离原则）
