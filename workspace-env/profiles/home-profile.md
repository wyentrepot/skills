# 🏠 家里环境 — Reasonix 配置参考

> 对应环境：纯 Windows 开发

## 可能涉及的配置项

```toml
# 家里环境 reasonix.toml 示例（草稿）
[agent]
reasoning_language = "zh-CN"

# Provider 配置（按实际使用的模型填写）
# [provider.deepseek]
# api_key_env = "DEEPSEEK_API_KEY"
# model = "deepseek-chat"
```

## 领域常量参考

> 以下常量可能需要根据家里环境设置，具体值见 [home-office.md](../home-office.md)。

| 常量 | 说明 |
|------|------|
| 工作根目录 | <!-- 待填 --> |
| COM 口 / 硬件路径 | <!-- 待填（如有） --> |
| 固件路径 | <!-- 待填（如有） --> |
| 工具链路径 | <!-- 待填（如有） --> |
| 代理配置 | <!-- 待填（如有） --> |

## 备注

- 加载方式整体方案**待定**，此处仅为配置参考草稿
- 具体常量值优先记录在 `home-office.md`，避免与流程混淆（遵循跨会话知识分离原则）