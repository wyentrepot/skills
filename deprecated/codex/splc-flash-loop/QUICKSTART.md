# SPLC STA/CCO V2 实机闭环 — 技能说明书

> 面向其他 AI 的快速上手指南。技能本体详细流程请见同目录 `SKILL.md`。

## 文件在哪

### 技能自身文件（`/root/.config/kilo/skills/splc-flash-loop/`）

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 技能本体（加载后 AI 获得完整操作指引） |
| `QUICKSTART.md` | **本文** — 技能说明书 |
| `INSTALL.md` | 安装部署指南 |

### WSL 侧

| 路径 | 说明 |
|------|------|
| `/home/H_STA/04/sta/` | STA 固件工程（venus2m），构建脚本 `bspmake.sh` |
| `/home/H_CCO/001/cco/` | CCO 固件工程（venus8m），构建入口 `Makefile` |
| `/home/ai_work/splc_tool/edbg_pc_debug_tool_full_source/` | EDBG 工具 Python 源码根目录（**所有命令在此执行**） |
| `edbg_pc/cli.py` | CLI 入口 |
| `edbg_pc/loop_orchestrator.py` | WSL 侧编排 |
| `edbg_pc/loop_worker.py` | Windows 侧串口操作 |
| `edbg_pc/loop_profile.py` | Profile 定义 |
| `tools/invoke_loop_worker.ps1` | PowerShell 桥脚本 |

### Windows 侧

| 路径 | 说明 |
|------|------|
| `D:\11-ai-workfile\sta\` | STA 证据日志 |
| `D:\11-ai-workfile\cco\` | CCO 证据日志 |
| `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` | Windows Python 3.12 |

### 通信架构

```
WSL python3 -m edbg_pc.cli loop {build|flash|...}
  → powershell.exe → Windows python312 loop-worker → 串口
```

## 核心命令（2 条完成闭环）

```bash
# 1. 编译
python3 -m edbg_pc.cli loop build --profile {sta-v2-hunan|cco-hunan}

# 2. 烧录 + 自动验证（返回结构化 JSON）
python3 -m edbg_pc.cli loop flash --profile {sta-v2-hunan|cco-hunan} --port {COM口}
```

`loop flash` 返回 JSON 含 `version`、`diqu`、`evidence`（证据日志路径）、`serial_log`。

## Profile 对照

| profile | 目标 | 端口 | 编译命令 | 包大小 | 波特率 | setmode |
|---------|------|------|----------|--------|--------|---------|
| `sta-v2-hunan` | STA venus2m | COM11 | `./bspmake.sh HU_NAN sta_venus2m` | 1024 | 115200→230400 | 否 |
| `cco-hunan` | CCO venus8m | 用户指定 | `make jump` | 1024 | 全程 115200 | 必须 |

## 其他命令

| 命令 | 作用 |
|------|------|
| `loop run --profile X` | 一键编译+烧录+验证 |
| `loop grab "关键字" --port X` | 抓日志直到关键字出现 |
| `loop capture --seconds N --port X` | 固定时长抓日志 |
| `loop test-run --suite all --debug-port COM11 --port COM4` | 跑 Unity 测试（仅 STA） |
| `loop doctor` | 预检环境 |

## bootloader 进入流程

`reboot` → 等 `Press 'd' key to enter bootloader mode!` → 发 `d` → `[root /]#`

**不要**在 `reboot` 后立即 spam 按键。CCO 倒计时约 3 秒。

## 已知工具 Bug（已修复）

使用中若遇到 `UnboundLocalError: local variable 'sys' referenced before assignment` 或 `worker response file not found`，需检查以下三处修复是否已应用：

1. **`cli.py:301`** — 删除局部 `import json, sys`（屏蔽全局 import，导致 Windows 端所有 `loop` 命令崩溃）
2. **`loop_orchestrator.py:342`** — PowerShell 调用补充 `-Profile` 参数（否则 Windows 端始终使用 `sta-v2-hunan`）
3. **`cli.py:318-354`** — `loop-worker` 端统一用 `req.get('profile') or req.get('profile_id') or args.profile` 解析 profile
