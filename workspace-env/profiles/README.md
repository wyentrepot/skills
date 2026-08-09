# profiles — Reasonix agent 配置参考

> 按 Reasonix 的 profile/config 机制，为每个工作环境准备一份 agent 配置参考。
> 每个文件描述该环境在 Reasonix 侧需要哪些配置（provider、权限、领域常量等）。

## 文件

| 文件 | 对应环境 |
|------|----------|
| [company-profile.md](./company-profile.md) | 🏢 公司（WSL + Windows 双环境） |
| [home-profile.md](./home-profile.md) | 🏠 家里（纯 Windows） |

## 说明

- Reasonix 配置优先级：`命令行参数 > 项目 reasonix.toml > 全局 config.toml > 内置默认值`
- 全局配置路径（Windows）：`%APPDATA%\reasonix\config.toml`
- 项目级配置：环境根目录下的 `reasonix.toml`
- 加载方式整体方案**待定**，此处为各环境的配置参考草稿。