# 上板烧录与验证（onboard-verify）

> 来源：0004 上板四件验收 + 0007 实机烧录复验。硬件：FC-3280T V3.0.3，boot ver_02-00-73。

## 串口环境（002 工程实测口径）

| 口 | 用途 | 波特率 |
|---|---|---|
| Windows COM9 → WSL /dev/ttyACM1（CH342 接口 02） | CCO 打印口 + boot 菜单 | 115200 8N1 |
| Windows COM8 → WSL /dev/ttyACM0（CH342 接口 00） | STA（同款板） | 115200 8N1 |
| COM4 → /dev/ttyUSB0（CP2102） | 对外通信口（uart1，模拟集中器侧） | 9600/115200 自适应 |

**双口职责从第一天分清**：厂测帧/通信帧发 ttyUSB0（uart1 对外口）；ttyACM1 只看日志和敲 boot 命令。
（0007 教训：把厂测帧发进打印口，终端回显被误判为板子应答，白耗半小时。）

WSL usbip 链路不稳（`urb->status -104`）时：Windows 侧 `usbipd detach --busid 6-2` 再 `attach --wsl --busid 6-2`，设备重枚举后 /dev/ttyACM* 接口序号不变（以 ID_USB_INTERFACE_NUM 为准，不以枚举顺序为准）。

## boot 菜单（上电倒计时 3 秒内）

```
Press 'd' key to enter bootloader mode!    → 按 'd' 进 [root /]#
Press '@' key to skip the waiting time and run image!  → 按 '@' 跳过直接跑固件
```

- `[root /]#` 视图命令：`image`（进镜像视图）/ `reboot` / `flash read|write` / `setmode` / `exit`。
- `[image /]#` 视图命令：`info` / `download 0|1` / `active 0|1` / `reboot`。
- 注意视图层级：`download`/`active` 在 **image 视图**下；固件 shell `[node /]$` 里没有这些命令。
- `download N` 后有 `Press <Y> to continue, or <N> to cancel` 确认提示——脚本化烧录必须处理，
  否则板子停死在提示符（0007 实测：停死后串口全静默，发 'N' 才救回来）。

## XMODEM-1K 串口烧录（pyserial 手搓协议，已验证零重传）

```python
# 握手：等 'C'；数据块: SOH/STX + blkno + ~blkno + 1024B + CRC16(XMODEM, poly 0x1021, init 0)
# 尾块补 0x1A 到 1024 整数倍；结束发 EOT(0x04) 等 ACK
# 490KB @115200 实测约 52s
```
流程：`reboot` → 'd' → `image` → `download 1` → 'Y' → 等 'C' → 发块 → EOT → `active 1` → `reboot`。

- 烧录中 System can't reset（提示明说）；XMODEM 等待期板子持续发 'C'，若全静默说明停在 Y/N。
- 大小窗口：iap 镜像 <512KB 槽位（实测 489~490KB 贴近上限，膨胀要警觉）。

## 验收四件（每版必过）

| # | 项 | 判据 |
|---|---|---|
| 1 | 版本串+交互 | `sdk_ver:ver_03-00-03-11`、shell 有应答 |
| 2 | flash 读写回环 | 32B/64B 写读逐字节全等（boot `flash write`） |
| 3 | IAP 升级全程 | XMODEM 下载→落 flash→active→重启加载运行 |
| 4 | 稳定观察 | `bsp init done!` 后业务任务起活，≥120s 零复位（判据要求 ≥6 分钟，建议过夜挂机） |

## 打点版方法论（卡死定位）

- 编 B2 打点版：卡死区间插 14 处 `LOG_SYNC`（仅 %u，无浮点），ELF 验证 probe 全部编入
  （教训：声称有 probe 实测 0 编入 = 白烧一次）。
- 二分定位：probe 走到哪条停 = 卡死点之后。
- **反汇编补强（0007 实证）**：编译级静默缺陷打点定位不到根因时，objdump -dr 拆库函数，
  核参数寄存器/结构体偏移/寄存器写序列——"编译过≠适配对"的最终裁决手段。

## 已知板上行为（对照用）

- `System reset by 8000 / SFT_GLB_RST` = 软件复位（reboot 命令），正常。
- 上电序：boot 横幅 → See OS run → `[node /]$` → bsp init done → rand_init tick 打印 →
  `fact test wait..`（300ms 厂测窗口，无数据则退）→ `iap wait...`（2s 窗口）→ 业务任务起活。
- 业务起活标志：`nwk_task try start network` 周期打印 / `mclt_state` / uart_com bpsCheck。
