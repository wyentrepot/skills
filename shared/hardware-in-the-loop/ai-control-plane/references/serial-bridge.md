# 串口桥（Windows COM ↔ WSL PTY）状态与验证

> 2026-10-22 起，ZZT_SELF 工作台串口默认走纯 Python 桥（Windows `serial_bridge.py
> windows` ↔ TCP ↔ WSL `serial_bridge.py wsl`），不再依赖 usbipd。
> **开任何串口会话前先做本页 preflight；桥不通时不要继续 ensure/open/verify。**

## 端点（工作台页面同级，loopback 免 token）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/serial-bridge/status` | 只读：桥进程、PTY 软链、数据/控制通道、映射匹配 |
| GET/POST | `/api/serial-bridge/verify` | 逐口验证；POST body `{"ports":["simcon"],"open":true}`，默认全部启用口 |
| — | `skills/share/serial-bridge/scripts/verify_bridge.py` | 技能自带客户端，`ok=true` 时退出码 0 |

```bash
curl -s http://127.0.0.1:8790/api/serial-bridge/status | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8790/api/serial-bridge/verify \
  -H 'Content-Type: application/json' -d '{}' | python3 -m json.tool
```

## 判读字段

| 字段 | 含义 |
|---|---|
| `ok` | 本次查询范围内全部启用口 `channel_ok`（verify 时要求 `workbench_ready`） |
| `summary` | `total/enabled/channel_ok/workbench_ready` 计数 |
| `ports[].channel_ok` | WSL 桥在跑 + PTY 软链是字符设备 + Windows 数据通道 + 控制通道 |
| `ports[].workbench_ready` | `channel_ok` 且 `serial_ports.json` 映射指向该软链、`parity=N` |
| `ports[].bridge.client_connected` | Windows 数据通道已连接 |
| `ports[].bridge.control_connected` | Windows 控制通道已连接（动态波特率依赖它） |
| `ports[].bridge.desired_baud` | WSL 应用当前要求的波特率（切换后 Windows 会跟随） |
| `ports[].mapping.baudrate` | `serial_ports.json` 映射的波特率；verify 按它打开 |
| `ports[].checks.open_ok` | pyserial 能以 `parity=N` 打开；`false` 看 `open_error` |
| `ports[].checks.in_use` | 端口已被工作台会话占用时跳过打开检查 |
| `ports[].warnings/errors` | 可直接向用户/上层报告的具体原因 |

一次成功的最小特征：`ok=true`、`summary.workbench_ready == summary.enabled`、
每个目标口 `checks.open_ok=true`。

## Preflight 顺序（AI 必须遵守）

1. `GET /api/health` 确认工作台在线。
2. `GET /api/serial-bridge/status`。
3. `ok=false` → **不要打开任何串口**；按 `ports[].errors` 报告是哪一层：
   - `wsl_bridge 未运行` → 先起 WSL 桥；
   - `Windows 侧数据/控制通道未连接` → Windows 桥没起或端口不通；
   - `桥接软链不存在` → WSL 桥没起/`link_dir` 不可写；
   - `工作台映射 ... 未指向桥接软链` / `parity 必须为 N` → 先改 `serial_ports.json`。
4. `POST /api/serial-bridge/verify`，确认目标口 `ok=true` 且 `workbench_ready=true`。
5. 再走既有接口：`module-actions` / `module-sessions` / `simcon` / `simeter`。
6. 结束会话后释放串口；Windows 用户要用口时先 `wsl stop`（释放全部桥端口）。

## 当前映射（2026-10-22 实机确认）

| mapping_id | Windows COM | WSL 路径 | 映射 baud | 物理参数 |
|---|---|---|---|---|
| `simcon` | COM4 | `/run/hplc/serial/simcon` | **9600** | 8E1（CCO 本地总线） |
| `cco-main` | COM8 | `/run/hplc/serial/cco-main` | 115200 | 8N1 |
| `sta-main` | COM9 | `/run/hplc/serial/sta-main` | 115200 | 8N1 |
| `listener` | COM11 | `/run/hplc/serial/listener` | 115200 | 8N1 |
| `factory` | COM7 | `/run/hplc/serial/factory` | 9600 | 8N1 |

> **⚠️ 2026-10-28 更正（以本表为准）**：原名记「cco-main=COM9 / sta-main=COM8 / listener=COM24 / simcon 9600」，
> 系 10-22 时**标签与实物相反**造成的误记。10-27 18:45 实机重定，10-27 20:07 已写入 `config/serial_ports.json`：
> **cco-main → 物理 COM8 = CCO 板；sta-main → 物理 COM9 = STA 板；listener COM24 → COM11（COM24 不存在）；simcon 9600 → 115200**。
> 旁证（日志文件名带串口号）：`data/logs/模块/cco/20261027-215846_[cco]_[cco-main-COM8-…]`、`sta/20261028-083511_[sta]_[sta-main-COM9-…]`。
> **唯一真相源是 `config/serial_ports.json`**，本表只作人读对照；代码/命令里一律用 `mapping_id`，**禁止硬编码 COM 号**。
> 原误记带来的教训：STA「调试口没 shell、reboot 无回显」曾据此误判一整夜，真因是 TX 线松（2026-10-28 08:33 修）。
- `config/serial_ports.json` 已切到上述路径；原 usbipd 配置备份：
  `config/serial_ports.json.usbipd-backup-20261022.json`。
- 映射 `parity` 必须为 `N`（PTY 不接受 PARENB）；真实 E 校验在
  `config/serial_bridge.json` 的 Windows 侧。

## COM4 / CCO bpsCheck 与 9600↔115200

CCO 只在上电/复位后跑 bpsCheck；`gSysPara.cac.local_rx_ok=1` 后不会重跑。
可用本地 1376.2 `01H-F1` 复位（CCO 回 `00H-F1`，约 7 秒后重启），然后用
14-F2 应答任务等待。

CCO 自适应序列（`data/logs/serial_bridge_evidence_20261022/`）：

- `bps:1` → 9600 E
- `bps:3` → 115200 N
- `bps:2` → 115200 E

实测：

- simcon 在 **9600** 等待：CCO 启动约 2 秒即 `bpsCheck affair over`；
- simcon 在 **115200 E** 等待：CCO 走完序列后成功；
- 9600 下 `10H-F2` 查询正常回帧。

注意：

- 匹配 14-F2 时 `fn` 用十进制 **2**，不是 242（`fn:242` 是另一个表示法，匹配不到）。
- **simcon 的映射 baud 必须与 CCO 当前落点一致**。verify 会按映射 baud
  打开 PTY，supervisor 再通过控制通道切换 Windows 物理口；不要用桥配置里的
  默认 115200 覆盖业务 baud。
- 应用改 `ser.baudrate` 时，WSL supervisor 轮询 PTY termios 并经控制口通知
  Windows 重开 COM；切换瞬间有几十毫秒中断，协议侧要能重试。

## 边界

- **人机交接**：`tools/scripts/wsl环境部署.bat` 菜单 **[6]** 一键启停 Python 桥
  （启动 = WSL supervisor + Windows `pythonw` 桥；停止只停 Windows 桥，立即释放 COM），
  **[7]** 查看桥状态。非交互：`uart-map.ps1 -Action bridge-toggle|bridge-start|bridge-stop|bridge-status`。
- **不依赖 usbipd / Hyper-V 防火墙**：桥走 Windows→WSL 的 TCP localhost；新版菜单
  [6]/[7] 不调用 usbipd，[3] 的 usbipd 视图有 3 秒超时。旧脚本若卡在防火墙检查，
  换用新版 `uart-map.ps1`。前提是 COM 在 Windows 侧可用（`Shared`/未 `Attached`）。
- **一口一主**：同一物理口同一时刻一个持有者；409/端口占用不是故障。
- **PTY 侧 parity=N**；真实 E/O 固定在 Windows 侧 `serial_bridge.json`。
- 无 DTR/RTS/流控；XMODEM 动态波特率未在桥上完整验证，烧录仍建议单档。
- Windows 桥必须常驻：会话级 `python.exe` 适合调试；长期用按项目技能
  `skills/share/serial-bridge/SKILL.md` 的「Windows 常驻」复制到 Windows
  本地目录后用 `pythonw.exe`。不要从 WSL 的 UNC 当前目录 `cmd start`。
- 若重新 usbipd attach：`serial_ports.json` 的 `usb_busid` 已清空；要么保持
  usbipd detached，要么恢复备份并停 WSL 桥。

## 故障速查

| 现象 | 处理 |
|---|---|
| `supervisor.running=false` | `python3 tools/serial_bridge/serial_bridge.py wsl start --config config/serial_bridge.json` |
| `client_connected=false` | Windows 桥没起，或 `windows.host`/端口不一致；见项目技能 |
| `control_connected=false` | 控制口（`tcp_port+1000`）被占用/未监听；动态波特率不可用 |
| `checks.open_ok=false` + `Invalid argument` | 用了 `parity="E"`；工作台/脚本改 `N` |
| `mapping.baudrate` 与 `desired_baud` 不一致 | verify 会按映射切换；先对齐业务/CCO 当前 baud |
| `wsl_bridge.lock` 被占用 | 已有实例；`wsl status` 看 pid，必要时 `wsl stop` |

## 相关

- 项目技能（部署/常驻/故障全量）：`skills/share/serial-bridge/SKILL.md`
- 配置：`config/serial_bridge.json`、`config/serial_ports.json`
- 实机证据：`data/logs/serial_bridge_evidence_20261022/`
