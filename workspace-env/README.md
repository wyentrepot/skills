# workspace-env — 工作环境介绍

> 用于记录**公司办公**与**家里办公**两套不同工作环境的差异，以及各自的加载方式。

## 环境总览

| 环境 | 类型 | 说明 | 详细文档 |
|------|------|------|----------|
| 🏢 公司办公 | WSL + Windows 双环境 | Linux（WSL）侧开发 + Windows 硬件侧 | [company-office.md](./company-office.md) |
| 🏠 家里办公 | 纯 Windows 开发 | 单系统开发环境 | [home-office.md](./home-office.md) |

## 核心差异

- **公司**：同一台机器上同时使用 **WSL（Linux）** 与 **Windows** 两套环境，涉及跨环境协同（如硬件、路径、工具链）。具体细节见 [company-office.md](./company-office.md)。
- **家里**：**纯 Windows** 开发环境，无 WSL 层，工具链/路径与公司不同。具体细节见 [home-office.md](./home-office.md)。

## 加载方式

> ⚠️ **状态：待定** —— 具体切换/加载方案后续再定。

候选方案（按 Reasonix 的 profile/config 机制组织，见 `profiles/`）：

1. **Reasonix 项目级配置**：每个环境可维护一份 `reasonix.toml`，通过 `reasonix --dir <环境根目录>` 加载。
2. **profile 参考文档**：`profiles/` 下为每个环境准备一份 agent 配置参考，说明该环境需要哪些 provider / 权限 / 常量。
3. **环境说明文档**：`company-office.md` / `home-office.md` 记录该环境的具体常量与差异，供 AGENTS.md / 会话引用。

> Reasonix 配置优先级：`命令行参数 > 项目 reasonix.toml > 全局 config.toml > 内置默认值`
> 全局配置路径（Windows）：`%APPDATA%\reasonix\config.toml`