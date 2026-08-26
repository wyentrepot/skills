---
name: opencode-mcp
description: 通过 Reasonix 调用 OpenCode MCP 工具，把编码任务、代码探索、代码审查委托给 OpenCode 的 zen-* agent 执行。Use when delegating coding tasks to OpenCode, delegating to zen-explorer/zen-worker/zen-reviewer agents, or driving OpenCode sessions from Reasonix.
---

# OpenCode MCP（Reasonix 定制版）

通过 Reasonix 内置的 `opencode` MCP server，将任务委托给 WSL 中的 OpenCode 执行。
底层链路：Reasonix → `wsl -d Ubuntu-22.04 -e bash /root/opencode-mcp/start-stdio.sh`（stdio）→ opencode-mcp 桥 → `http://127.0.0.1:4097` 的 opencode serve。

## 前提

- WSL（Ubuntu-22.04）必须运行，且 `opencode serve`（端口 4097）在线。若 4097 未监听，先启动：
  ```bash
  wsl -d Ubuntu-22.04 -e bash -lc "nohup opencode serve --hostname 127.0.0.1 --port 4097 > /root/.config/opencode/serve-4097.log 2>&1 < /dev/null &"
  ```
- MCP 已注册为 Reasonix 全局 `[[plugins]] opencode`（stdio），工具名以 `opencode_` 为前缀。

## 可用工具

| 类别 | 工具 |
|------|------|
| 执行 | `opencode_run`（单次编码任务）、`opencode_session_create`、`opencode_session_prompt`、`opencode_session_list`、`opencode_session_abort` |
| 文件 | `opencode_file_read`、`opencode_file_search`、`opencode_find_files`、`opencode_find_symbols` |
| 配置 | `opencode_model_list`、`opencode_model_configure`、`opencode_provider_list`、`opencode_config_get`、`opencode_config_update` |
| Agent | `opencode_agent_list`、`opencode_agent_delegate` |
| 技能 | `opencode_skill_list`、`opencode_skill_create` |
| MCP | `opencode_mcp_list`、`opencode_mcp_enable` |
| 工具 | `opencode_tool_list` |

## 何时使用

- **实现/重构/调试**：`opencode_run`
- **代码探索（只读）**：`opencode_agent_delegate` + `agent="zen-explorer"`
- **小改动 + 受限验证命令**：`opencode_agent_delegate` + `agent="zen-worker"`
- **代码审查（只读）**：`opencode_agent_delegate` + `agent="zen-reviewer"`
- **多轮任务需上下文**：`opencode_session_create` + `opencode_session_prompt`

> 本环境的 opencode.json 只定义了 `zen-explorer` / `zen-worker` / `zen-reviewer` 三个 subagent，**没有**上游文档里的 `build` / `plan` / `explore`。委托时务必传 `zen-*`。

## 委托示例（本环境可用 agent）

```json
opencode_agent_delegate({
  "agent": "zen-explorer",
  "prompt": "Find all places that read the serial config and summarize the flow"
})

opencode_agent_delegate({
  "agent": "zen-worker",
  "prompt": "Add a unit test for parse_config() and run npx vitest run tests/unit"
})

opencode_agent_delegate({
  "agent": "zen-reviewer",
  "prompt": "Review the pending diff in this repo; report findings with file:line"
})
```

## 单次编码任务

```json
opencode_run({
  "prompt": "Implement X with tests",
  "workingDirectory": "/01-workfile-ai/02-gent-work",
  "agent": "zen-worker"
})
```

- 默认工作目录为 `OPENCODE_DEFAULT_PROJECT=/01-workfile-ai/02-gent-work`；显式 `workingDirectory` 优先。
- 默认模型为 `opencode/mimo-v2.5-free`；可用 `model` 覆盖（见下方「可用模型」）。

## 可用模型（已实测验证）

以下模型均通过本链路真实推理验证可用（2026-08-26）：

### 免费模型（7 个，全部实测 ✅）
| 模型 id | 名称 |
|---------|------|
| `opencode/big-pickle` | Big Pickle (Free) |
| `opencode/x-preview-f-free` | Ox Alpha Free（Unlimited） |
| `opencode/mimo-v2.5-free` | MiMo-V2.5 Free（默认） |
| `opencode/hy3-free` | Hy3 Free |
| `opencode/nemotron-3-ultra-free` | Nemotron 3 Ultra Free |
| `opencode/nemotron-3.5-lightning-free` | Nemotron 3.5 Lightning Free |
| `opencode/muse-spark-1.2-contributor-free` | Muse Spark 1.2 Contributor Free |

### 付费/主力模型（部分实测 ✅）
| 模型 id | 名称 |
|---------|------|
| `opencode/claude-opus-4-7` | Claude Opus 4.7（实测✅） |
| `opencode/kimi-k2.7-code` | Kimi K2.7 Code（实测✅） |
| `opencode/claude-opus-4-8` | Claude Opus 4.8 |
| `opencode/claude-opus-5` | Claude Opus 5 |
| `opencode/claude-sonnet-5` | Claude Sonnet 5 |
| `opencode/gpt-5.6-sol` | GPT-5.6 Sol |
| `opencode/gpt-5.6-terra` | GPT-5.6 Terra |
| `opencode/gemini-3.7-flash` | Gemini 3.7 Flash |
| `opencode/gemini-3.5-flash` | Gemini 3.5 Flash |
| `opencode/deepseek-v4-flash` | DeepSeek V4 Flash |
| `opencode/deepseek-v4-pro` | DeepSeek V4 Pro |
| `opencode/glm-5.2` | GLM-5.2 |
| `opencode/qwen3.6-plus` | Qwen3.6 Plus |
| `opencode/grok-4.6` | Grok 4.6 |

> 完整清单可随时用 `opencode_model_list({ "provider": "opencode" })` 拉取（62 个）。
> 免费模型注意可能有限流/排队；付费模型消耗 Zen 额度。

## 模型选择与派发逻辑

### 免费模型能力与隐私（来源：opencode.ai/docs/zen，2026-08-26）

| 模型 id | 厂商/底座 | 官方定性 | 数据隐私 |
|---------|----------|---------|---------|
| `opencode/mimo-v2.5-free` | 小米 Xiaomi | 通用模型，限时免费收集反馈 | **数据可能用于改进模型** |
| `opencode/nemotron-3-ultra-free` | NVIDIA | NVIDIA 免费端点 Trial | **Trial 使用，禁止敏感数据；会话被记录** |
| `opencode/nemotron-3.5-lightning-free` | NVIDIA | NVIDIA 免费端点 Trial | 同上，禁止敏感数据 |
| `opencode/muse-spark-1.2-contributor-free` | Meta | Muse Spark 贡献者层，重度折扣换训练权 | **prompt 用于训练 Meta 模型**；限速 100 RPM |
| `opencode/big-pickle` | 未公开（stealth 隐身模型） | 隐身模型，限时免费 | **数据可能用于改进模型** |
| `opencode/x-preview-f-free` | 未公开（stealth） | 隐身模型（Ox Alpha） | 零保留（provider 不训练） |
| `opencode/hy3-free` | 未公开 | 限时免费收集反馈 | 数据可能用于改进模型 |

> 另有 `opencode/laguna-s-2.1-free`（新出现的免费模型）。

### 免费模型适合的任务（推荐映射）

| 任务类型 | 推荐免费模型 | 理由 |
|---------|-------------|------|
| 只读探索 / 代码定位 / 快速问答 | `mimo-v2.5-free`（默认） | 通用免费、够用、零成本 |
| 简单代码生成 / 格式化 / 注释 / 单测骨架 | `mimo-v2.5-free` 或 `hy3-free` | 轻量任务，免费档足够 |
| 无需联网的脚本 / 机械改动 | `mimo-v2.5-free` | 省额度 |
| 复杂推理 / 多步调试 / 重构 | 免费模型较弱 → 建议付费（`kimi-k2.7-code` / `claude-opus-4-7`） | 免费档不擅长长链条 |
| 代码审查 / 高价值正确性 | 付费（`claude-opus-4-7`） | 免费档正确性风险高 |
| **敏感/公司机密代码** | ⚠️ 避免免费模型 | 多数免费模型数据可能被厂商记录/训练；机密代码请用付费或自备 key |

### 派发决策（model × agent）

- **未指定 `model` 时**：走默认 `opencode/mimo-v2.5-free`（`OPENCODE_DEFAULT_MODEL`），零成本。
- **指定 `model` 时**：在 `opencode_run` / `opencode_session_create` / `opencode_agent_delegate` 传 `"model": "opencode/<id>"` 覆盖默认。
- **派发（谁执行）由 `agent` 决定，与 `model` 正交**：
  - `zen-explorer`（只读探索）→ 免费 `mimo-v2.5-free` 即可
  - `zen-worker`（改代码+受限命令）→ 简单改动用免费；重要改动用 `opencode/kimi-k2.7-code`
  - `zen-reviewer`（代码审查）→ `opencode/claude-opus-4-7` 强推理
- **经验法则**：免费模型适合「探索、简单生成、低风险机械活」；「复杂推理、审查、机密代码」用付费模型。模型与 agent 独立设置，不自动互推。

## 会话管理（多轮）

```json
// 创建会话
opencode_session_create({ "title": "auth-refactor", "workingDirectory": "/01-workfile-ai/02-gent-work" })
// 持续对话
opencode_session_prompt({ "sessionId": "<id>", "prompt": "继续，把错误处理也加上" })
// 列出/中止
opencode_session_list({})
opencode_session_abort({ "sessionId": "<id>" })
```

## 配置查询

```json
opencode_model_list({ "provider": "opencode" })
opencode_agent_list({})
opencode_config_get({})
```

## 注意

- `opencode_run` 会等待任务完成并返回结果，超时上限受 `OPENCODE_TIMEOUT`（120s）约束；长任务建议用 `session_create` + `session_prompt`。
- `opencode_mcp_list` / `opencode_mcp_enable` / `opencode_skill_create` 是半实现（只返回配置指引，不真正落盘）。
- `opencode_model_list` 可能有 zod 校验告警（models 为对象格式），但不影响返回。
- 安全：opencode serve 仅绑定 loopback；`auth.json` 0600；不要向日志/提示词泄露 opencode API key。
