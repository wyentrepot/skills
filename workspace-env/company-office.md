# 🏢 公司办公环境 — WSL + Windows 双环境

> 环境类型：**同一台机器同时使用 WSL（Linux）与 Windows 两套环境**。

## 概览

- **操作系统**：Windows（宿主）+ WSL2（Linux）双环境
- **特点**：跨环境协同，涉及 Linux 侧开发与 Windows 硬件侧操作

## Linux（WSL）侧

| 项 | 值 / 说明 |
|----|-----------|
| WSL 发行版 | Ubuntu 22.04.5 LTS（WSL2，内核 `6.6.87.2-microsoft-standard-WSL2`） |
| 用户 / Shell | `root` / `/bin/bash` |
| 工作根目录（WSL） | `/home`（各项目独立，见下表） |
| 语言 / 工具链 | Python 3.10.12；Node v22.23.1；gcc 11.4.0；GNU Make 4.3；git 2.34.1；RISC-V 工具链 `riscv64-unknown-elf-gcc (V1.12.0) 8.4.0`（位于 `/opt/riscv64-elf-x86_64/bin/`） |
| 编码规范索引 | `/home/rule/project-index/cco/`（`coding-standards.mdc`、`source-map.mdc`、`log-analysis.mdc`、`INDEX.mdc`） |

### 关键项目路径（WSL）

| 路径 | 用途 |
|------|------|
| `/home/H_STA/04/sta` | STA 固件主树（`protocol/aps/diqu_conf.h`、`yxsm_conf.h`、`Makefile`） |
| `/home/H_CCO/001/cco` | CCO 固件主树 |
| `/home/kilo/edbg_pc_debug_tool_full_source` | SPLC EDBG 闭环工具运行时（`python3 -m edbg_pc.cli loop ...`） |
| `/home/H_STA/py_manage/moduleparasconfigtool` | 上位机配置工具 |
| `/home/H_CCO/minute_collection_workflow` | 分钟采集工作流 |

### 证据目录（WSL）

| 路径 | 用途 |
|------|------|
| `/d/sta/<project-name>/` | STA 烧录证据 + 持久设置（readme） |
| `/d/cco/<project-name>/` | CCO 烧录证据 + 持久设置（readme） |

对应示例：`/d/sta/04-sta/`、`/d/cco/001-cco/`。readme 无后缀名（如 `/d/cco/001-cco/readme-cco-hunan`），烧录证据按时间戳子文件夹归档（如 `/d/sta/04-sta/20260729-095818/`）。

## Windows 侧

| 项 | 值 / 说明 |
|----|-----------|
| 工作根目录（Windows） | `D:\`（WSL 挂载于 `/mnt/d`，9p/drvfs） |
| 硬件 / 外设 | 串口（COM 口，CH341/CP210x 适配器）、烧录器、目标板 |
| 工具链 | Windows 侧：Reasonix / Codex / Parasoft 等；硬件操作侧工具 |

> Windows 盘符经 `/mnt/<盘符>` 在 WSL 中访问：`D:\` ↔ `/mnt/d`。

## 跨环境要点

- **路径映射**：WSL 原生路径（`/home`、`/d`）与 Windows 盘符互访；Windows 盘符经 `/mnt/` 挂载点访问。
- **工作划分**：代码编译/烧录/证据采集在 WSL（Linux）侧完成；上位机配置、Reasonix 会话、串口硬件枚举可在 Windows 侧完成。
- **串口交叉验证**（Windows 侧）：
  ```powershell
  [System.IO.Ports.SerialPort]::GetPortNames()
  Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description
  Get-PnpDevice -Class Ports -PresentOnly
  Get-ItemProperty 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM'
  ```
- **证据落盘**：烧录/采集日志统一保存到 WSL 的 `/d/<sta|cco>/<project>/<时间戳>/`，不混入 Windows 侧旧档案。
