# SPLC Flash Loop — 固件烧录闭环技能 · 安装指南

> 给其他 Reasonix AI 安装此技能时使用。

## 技能概述

`splc-flash-loop` 是一个 SPLC STA 固件烧录闭环技能，工作流程：

```
发现最新固件产物 → 用户确认 → 烧录 → 抓日志 → 异常处理
```

支持三种场景：快速烧录、测试固件烧录 + 日志抓取、仅抓日志。

---

## 1. 前置条件

| 组件 | 要求 |
|------|------|
| WSL | Ubuntu-22.04 发行版 |
| Windows Python | 3.10+（安装脚本会自动安装/检查） |
| pyserial | `pip install pyserial`（安装脚本自动处理） |
| WSL→Windows 桥接 | WSL 中可调用 `powershell.exe` |

---

## 2. 安装方法（给 Reasonix AI）

> 此技能已注册为 **全局技能**（`C:\Users\<用户名>\AppData\Roaming\reasonix\skills\splc-flash-loop\SKILL.md`）。

### 2.1 对 Reasonix AI 说：

```
/install-skill splc-flash-loop
```

或直接调用：

```
@reasonix 使用 splc-flash-loop 技能
```

### 2.2 手动注册（如果技能未出现在列表中）

在 Reasonix 中执行：

```
/install-capability
```

来源选择：`C:\Users\<用户名>\AppData\Roaming\reasonix\skills\splc-flash-loop\`

或使用 `install_source` 工具：

```json
{
  "source": "C:\\Users\\<用户名>\\AppData\\Roaming\\reasonix\\skills\\splc-flash-loop\\",
  "kind": "skill",
  "scope": "global"
}
```

### 2.3 验证安装

技能加载后，在 Reasonix 中应能看到 `/splc-flash-loop` 可用命令。

---

## 3. 关键路径一览

### WSL 侧 — 工具脚本

> **⚠️ 重要**：其他 AI 的 WSL 可能没有 `/home/tool_skill/` 目录。**必须先将整个目录复制过去**。

| 路径 | 说明 |
|------|------|
| `/home/tool_skill/` | 工具脚本根目录（需手动复制） |
| `/home/tool_skill/flash_and_log.sh` | 主入口脚本 |
| `/home/tool_skill/win_bridge.sh` | WSL→Windows PowerShell 桥接 |
| `/home/tool_skill/serial_bridge.py` | Python 串口桥接（源码副本） |
| `/home/tool_skill/setup.sh` | WSL 侧一键安装脚本 |
| `/home/tool_skill/setup_windows.ps1` | Windows 侧安装脚本 |
| `/home/tool_skill/config.example.sh` | 配置模板 |
| `/home/tool_skill/SKILL.md` | 技能描述文件 |

### Windows 侧 — 运行时

| 路径 | 说明 |
|------|------|
| `D:\code\01-ai-tool\serial_bridge.py` | Python 串口桥接服务（由 setup 脚本复制） |
| `D:\code\01-ai-tool\bridge_config.json` | 自动生成的配置信息 |
| `D:\code\01-ai-tool\*` | 烧录日志输出目录 |

### 固件产物路径

| 路径 | 说明 |
|------|------|
| `/home/H_STA/04/sta/firmware/sta_venus2m_v7/*iap*.bin` | STA V2 最新固件产物 |

### 日志

| 路径 | 说明 |
|------|------|
| `D:\code\01-ai-tool\{YYYYmmdd-HHMMSS}` | 每次烧录生成的日志文件 |

---

## 4. 环境部署步骤

### 4.1 复制工具脚本到 WSL

如果目标 AI 的 WSL 中没有 `/home/tool_skill/`，从本机复制：

```bash
# 在本机导出
scp -r /home/tool_skill/ user@target-wsl:/home/tool_skill/
```

或在目标 WSL 中手动创建并复制以下文件：
- `flash_and_log.sh`
- `win_bridge.sh`
- `serial_bridge.py`
- `setup.sh`
- `setup_windows.ps1`
- `config.example.sh`
- `SKILL.md`

### 4.2 WSL 侧一键安装

```bash
cd /home/tool_skill/
bash setup.sh
```

`setup.sh` 会自动：
1. 检查 `powershell.exe` 桥接通道
2. 调用 `setup_windows.ps1` 配置 Windows 侧
3. 检查 WSL 基础工具（cat、timeout）
4. 验证桥接通道
5. 创建默认配置 `my_config.sh`

### 4.3 手动 Windows 部署（若自动部署失败）

在 **Windows PowerShell** 中执行：

```powershell
# 创建目录
mkdir D:\code\01-ai-tool -Force

# 复制桥接脚本
copy \\wsl.localhost\Ubuntu-22.04\home\tool_skill\serial_bridge.py D:\code\01-ai-tool\

# 运行 Windows 安装脚本
powershell -NoProfile -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-22.04\home\tool_skill\setup_windows.ps1
```

### 4.4 验证安装

```bash
# 在 WSL 中验证桥接
bash /home/tool_skill/win_bridge.sh doctor
```

---

## 5. 使用示例

### 通过 Reasonix AI 使用

启动技能后，AI 会引导交互流程：

```
/splc-flash-loop
```

AI 首先询问场景：
1. 04工程 快速烧录 (COM23, STA V2 最新产物)
2. 测试固件烧录 (COM23 烧录 + COM4 收测试日志)
3. 仅抓日志
4. 自定义

### 直接使用脚本

```bash
# 交互模式
bash /home/tool_skill/flash_and_log.sh

# 配置文件模式
cp config.example.sh my_config.sh
# 编辑 my_config.sh 填入参数
bash /home/tool_skill/flash_and_log.sh my_config.sh
```

### 配置模板示例

```bash
# 固件产物路径
FW_PATH="/home/H_STA/04/sta/firmware/sta_venus2m_v7/*.bin"

# 串口（COM* → 桥接模式走 Windows Python；/dev/* → 直接模式走 Linux 串口）
PORT="COM23"

# 烧录命令模板
FLASH_CMD="python3 -m edbg_pc.cli loop flash --file {path} --port {port}"

# 日志保存路径
LOG_DEST="/mnt/d/code/01-ai-tool/"

# 关键字抓日志（匹配即停）
GRAB_KEYWORD="sta main task run"
```

---

## 6. 架构说明

```
┌─────────────────────────────────────────────────────────────────┐
│  WSL 侧 (/home/tool_skill/)                                    │
│                                                                 │
│  flash_and_log.sh  ── 主入口（双模式自动切换）                   │
│       │                                                         │
│       ├── 直接模式 (PORT=/dev/*)                                │
│       │     └── cat / screen / picocom → 串口                  │
│       │                                                         │
│       └── 桥接模式 (PORT=COM*)                                  │
│             └── win_bridge.sh ── PowerShell 桥接                │
│                                    │                            │
└────────────────────────────────────┼────────────────────────────┘
                                     │ powershell.exe
┌────────────────────────────────────┼────────────────────────────┐
│  Windows 侧 (D:\code\01-ai-tool\)  │                            │
│                                     ▼                           │
│  serial_bridge.py  ←── Python 串口桥接服务                      │
│       │                                                         │
│       ├── doctor      预检环境                                  │
│       ├── flash       烧录固件                                  │
│       ├── grab        关键字抓日志（匹配即停）                   │
│       ├── capture     固定时长抓日志                             │
│       ├── send        发送串口命令                               │
│       └── list-ports  列出可用串口                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. 常见问题

### 7.1 找不到 `/home/tool_skill/`

**A**：这是 WSL 侧的本地目录，需要手动创建并复制文件。见第 4.1 节。

### 7.2 Image download failed / -3

**原因**：X-Modem 握手失败，板子不在 bootloader 模式。
**解决**：检查板子是否处于烧录模式，重新上电后重试。

### 7.3 Port not found

**原因**：串口被占用或不存在。
**解决**：执行 `python D:\code\01-ai-tool\serial_bridge.py list-ports` 查看可用端口。

### 7.4 ModuleNotFoundError

**原因**：Python 环境问题。
**解决**：在 Windows 中执行 `pip install pyserial`，然后重试。

### 7.5 超时无输出

**原因**：板子供电或串口连接问题。
**解决**：检查板子供电、串口线连接、波特率设置。

---

## 8. 路径速查表

| 用途 | WSL 路径 | Windows 路径 |
|------|----------|-------------|
| 工具脚本 | `/home/tool_skill/` | — |
| 技能定义 | — | `%APPDATA%\reasonix\skills\splc-flash-loop\` |
| Python 桥接 | `/home/tool_skill/serial_bridge.py` | `D:\code\01-ai-tool\serial_bridge.py` |
| 日志输出 | `/d/code/01-ai-tool/` | `D:\code\01-ai-tool\` |
| 固件产物 | `/home/H_STA/04/sta/firmware/sta_venus2m_v7/` | — |
| WSL 配置 | `/home/tool_skill/my_config.sh` | — |
| 安装配置 | — | `D:\code\01-ai-tool\bridge_config.json` |
| Windows 安装脚本 | `/home/tool_skill/setup_windows.ps1` | — |

---

## 9. 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 配置加载失败 |
| 2 | 预检失败 |
| 3 | 烧录失败 |
| 4 | 抓日志失败 |

---

*此 README 由 `splc-flash-loop` 技能自动生成。*
