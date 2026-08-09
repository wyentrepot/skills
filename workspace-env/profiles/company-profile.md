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

> 以下常量可能需要根据公司环境设置，具体值见 [company-office.md](../company-office.md)。

| 常量 | 说明 |
|------|------|
| WSL 发行版 | <!-- 待填 --> |
| Linux 工作根目录 | <!-- 待填 --> |
| Windows 工作根目录 | <!-- 待填 --> |
| COM 口 / 硬件路径 | <!-- 待填（如有） --> |
| 固件路径 | <!-- 待填（如有） --> |
| 代理配置 | <!-- 待填（如有） --> |

## 备注

- 加载方式整体方案**待定**，此处仅为配置参考草稿
- 具体常量值优先记录在 `company-office.md`，避免与流程混淆（遵循跨会话知识分离原则）