---
name: serial-flash-session
description: 编排 ZZT_SELF 模块日志/烧录串口（ModuleSerialService）：串口全程实时监控 + 同一串口上执行 XMODEM 模块烧录，烧录不打断实时监控。用 REST API 启动服务 → 选模块日志 COM → 配置串口 → 触发烧录（页面按钮或脚本双入口）→ 实时查看 → 停止 → 取日志路径。取代 xmodem-module-flash 的编排职责。
---

# serial-flash-session — 串口全程监控 + XMODEM 烧录一体化编排层

本技能是**编排层**（薄封装）：复用 ZZT_SELF 引擎（D:\zzt）的 ModuleSerialService REST API，避免重复实现串口/XMODEM 逻辑。

> 依赖：ZZT_SELF 项目已运行（FastAPI 127.0.0.1:8765），且已包含 hplc_web/module_serial_service.py、hplc_web/xmodem_flash.py、前端 /module-serial 页面。

## 核心模型（必须先理解）

- **串口单一模块模型**：ModuleSerialService 是唯一持有「模块日志/烧录串口」handle 的地方。前端、本技能都只通过 REST API 下发指令，不直接持有串口。
- **常驻独占**：start 打开一次、stop 关闭；烧录、改波特率、手动写都在这一个 handle 上，不关串口、不重开。
- **烧录 = 文件传输**：同一 handle 上 XMODEM 传输 + 动态切波特率，RX 监控线程全程不停 → 烧录前/烧录中/烧录后日志是同一条时间线。
- **与侦听台完全独立**：另一套 COM、另一套数据处理，互不干扰。
- **双入口**：页面按钮（前端 /module-serial）与脚本/API 走同一执行路径（都调 /api/module-serial/flash）。

## 编排流程

### A. 确认服务在运行
- 检查 GET http://127.0.0.1:8765/api/version 返回含 module_serial_api_revision。
- 未运行：提示用户先启动 ZZT_SELF（python hplc_web/run.py），不要直接用本技能硬开串口（那是 flash_module.py 项目不在时的兜底）。

### B. 选串口并启动
1. GET /api/module-serial/ports → 列出可用 COM。
2. 未确认 COM 口不烧录（安全规则）：向用户展示列表让其选择，绝不擅自选。
3. POST /api/module-serial/start {"port":"COM7","baudrate":9600,...}。
4. 确认 GET /api/module-serial/status state=running。

### C. 配置串口（可选）
- 手动写字节：POST /api/module-serial/write {"data":"AA BB CC"}。
- 改波特率：POST /api/module-serial/baudrate {"baudrate":115200}。

### D. 触发烧录
- 首选：引导用户在 /module-serial 页面选择 .bin + slot + 波特率方案，点「开始烧录」（页面按钮入口）。
- 或直接调 POST /api/module-serial/flash {"bin_path":"D:\fw\app.bin","slot":0,"baud_plan":[9600,115200,9600],"no_reboot_after":false}。
- 烧录在线程中执行，立即返回；进度靠 GET /api/module-serial/status 的 flash 字段轮询（packet/total/phase）。

### E. 实时查看
- 前端页面实时滚动日志（800ms 增量轮询）。
- 或轮询 GET /api/module-serial/logs?after=<last_seq> 增量拉取。

### F. 停止并取日志
- POST /api/module-serial/stop。
- 日志文件在 GET /api/module-serial/status 的 log_file（LOG/MODCOM*.txt），跨天轮转，与侦听台互不干扰。

## 安全规则（继承 xmodem-module-flash，必须遵守）

- 未确认 COM 口不烧录：必须由用户明确指定端口，绝不自动选择。
- dry-run / 自检不算硬件证据：flash_module.py --dry-run 或 --selftest 通过只证明参数/CRC 正确，不等于烧录成功。
- 烧录成功须有 bootloader 确认文本：XMODEM 传输完必须等到 Image download OK（或 download ... success）文本才判定成功；无该文本视为失败，不得谎报 BURN SUCCESS。
- 固件 .bin 必须真实存在；路径可用 Windows / WSL / UNC 形式。

## 独立兜底（项目不在运行时）

ZZT_SELF 不在运行时，才用独立脚本（自己 open COM，用完即关，复用同一核心）：



但优先用上面 A-F 的项目内编排（运行时项目已独占串口，脚本会冲突）。

## 参考
- 设计文档：docs/serial-flash-session-design.md（权威）
- 引擎：hplc_web/module_serial_service.py、hplc_web/xmodem_flash.py
- 独立脚本：flash_module.py
