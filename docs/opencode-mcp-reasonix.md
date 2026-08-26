# OpenCode MCP × Reasonix 集成总结

> 汇总日期：2026-08-26
> 目的：记录 Reasonix（Windows 桌面）通过 WSL 使用 OpenCode MCP 的完整方案、已实测结论与已知问题。

## 一、整体架构（当前生效）

```
Reasonix (Windows)
  └─ opencode MCP server (stdio, 注册于全局 config.toml)
       └─ wsl -d Ubuntu-22.04 -e bash /root/opencode-mcp/start-stdio.sh
            └─ opencode-mcp 桥 (node dist/index.js, 默认 stdio)
                 └─ opencode serve (http://127.0.0.1:4097, WSL 内)
                      └─ OpenCode Zen (opencode.ai/zen)
```

- **连接方式**：stdio via WSL。Reasonix 按需拉起 WSL 内的 node 进程，**无需在 Windows 侧安装 Node.js**。
- **注册位置**（Reasonix 全局配置）`~/AppData/Roaming/reasonix/config.toml`：
  ```toml
  [[plugins]]
  name    = "opencode"
  command = "wsl"
  args    = ["-d", "Ubuntu-22.04", "-e", "bash", "/root/opencode-mcp/start-stdio.sh"]
  ```
- **启动脚本** `/root/opencode-mcp/start-stdio.sh`：设 `OPENCODE_SERVER_URL=http://127.0.0.1:4097`、`OPENCODE_DEFAULT_MODEL=opencode/mimo-v2.5-free`、`OPENCODE_DEFAULT_PROJECT=/01-workfile-ai/02-gent-work` 后 `exec node dist/index.js`。

## 二、MCP 能力

- 注册工具 **21 个**（`opencode_*` 前缀），经 `reasonix-cli doctor capabilities --live` 实测 `runtime_status=probed`、`tool_count=21`。
- 分类：
  - 执行：`opencode_run`、`opencode_session_create/prompt/list/abort`
  - 文件：`opencode_file_read/search`、`opencode_find_files/symbols`
  - 配置：`opencode_model_list/configure`、`opencode_provider_list`、`opencode_config_get/update`
  - Agent：`opencode_agent_list`、`opencode_agent_delegate`
  - 技能 / MCP / 工具：`opencode_skill_list/create`、`opencode_mcp_list/enable`、`opencode_tool_list`

## 三、可用模型（已实测）

- 默认模型：`opencode/mimo-v2.5-free`（零成本）。
- 免费模型 **7 个全部实测可用**：`big-pickle`、`x-preview-f-free`、`mimo-v2.5-free`、`hy3-free`、`nemotron-3-ultra-free`、`nemotron-3.5-lightning-free`、`muse-spark-1.2-contributor-free`（另有新出现的 `laguna-s-2.1-free`）。
- 付费/主力已实测：`claude-opus-4-7`、`kimi-k2.7-code`。
- 完整清单：`opencode_model_list({ "provider": "opencode" })`（约 62 个）。

### 免费模型身份与隐私（来源 opencode.ai/docs/zen）

| 模型 | 厂商 | 数据隐私 |
|------|------|---------|
| `mimo-v2.5-free` | 小米 Xiaomi | 数据可能用于改进模型 |
| `nemotron-3-ultra-free` / `nemotron-3.5-lightning-free` | NVIDIA | Trial，禁止敏感数据，会话被记录 |
| `muse-spark-1.2-contributor-free` | Meta | prompt 用于训练 Meta 模型，限速 100 RPM |
| `big-pickle` / `hy3-free` | 未公开（stealth） | 数据可能用于改进模型 |
| `x-preview-f-free` | 未公开（stealth） | 零保留 |

> ⚠️ **敏感/公司机密代码请勿使用免费模型**（多数会记录/训练数据）。

## 四、任务派发规则（模型 × agent）

- **模型（model）与派发（agent）正交**：agent 决定"谁以什么权限执行"，model 决定"底层用哪个大模型"。
- agent：本环境仅 `zen-explorer`（只读探索）、`zen-worker`（改代码+受限命令）、`zen-reviewer`（只读审查）。
- 推荐映射见技能文档 `reasonix/opencode-mcp/SKILL.md`。

## 五、技能

- **`opencode-mcp` 技能**（Reasonix 定制版）已随本仓库发布至 `reasonix/opencode-mcp/SKILL.md`。
- 全局已安装于 `~/AppData/Roaming/reasonix/skills/opencode-mcp/SKILL.md`（doctor 实测 `scope=global, status=winner`）。

## 六、依赖与运维

- **WSL 必须运行**，且 `opencode serve`（4097）必须在线；4097 挂掉则 MCP 不可用。
- **systemd 托管（待 WSL 重启生效）**：
  - `/etc/wsl.conf` 已加 `[boot] systemd=true`（备份 `wsl.conf.bak-pre-systemd`）
  - `/etc/systemd/system/opencode-serve.service`：托管 4097
  - 引导脚本 `/root/setup-opencode-services.sh`：WSL 重启后跑一次 → `systemctl enable+start opencode-serve.service`，此后每次重启自动托管 4097。
- 验证命令：`D:\tools\Reasonix\versions\v1.31.4\reasonix-cli.exe doctor capabilities --live --json`

## 七、已知问题/注意

1. **opencode-mcp 的 HTTP transport 有上游 bug**（stateless 多客户端 `Already connected to a transport`），**勿用 HTTP 模式**；stdio 完全正常。
2. `opencode_mcp_list/enable`、`opencode_skill_create` 是半实现（只返回指引不落盘）。
3. `opencode_model_list` 有 zod 校验告警（models 为对象格式），不影响返回。
4. Reasonix CLI 不在 PATH：`D:\tools\Reasonix\versions\v1.31.4\reasonix-cli.exe`。
5. 免费模型有限流/排队，付费模型消耗 Zen 额度。
