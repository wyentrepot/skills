---
name: splc-flash-loop
description: 构建、烧录并验证 SPLC STA/CCO V2 固件，使用现有 EDBG 闭环工具保存工程级证据和按 profile 隔离的持久参数。适用于 STA venus2m、CCO venus8m、版本与地区验证、串口证据采集、环境诊断及 STA Unity 测试。
---

# SPLC STA/CCO V2 实机闭环

本文件是此技能的权威说明。`QUICKSTART.md` 和 `INSTALL.md` 是旧资料；若与本文件或当前 CLI 不一致，以本文件和当前运行时为准。

## 运行时与输出控制

在 WSL 中使用现有运行时：

```bash
cd /home/kilo/edbg_pc_debug_tool_full_source
python3 -m edbg_pc.cli loop --help
```

除非用户明确要求修改工具本身，否则不得复制或修改该目录内的运行时代码。

构建、Unity 和长时间串口输出必须重定向到所选工程的 `/d/...` 证据目录，不要把完整日志载入 AI 上下文，也不要使用 `tee`。成功时只返回退出码、耗时、必要结果字段、产物及证据路径；失败时只展开首个根因附近的有限上下文（默认最多 80 行、每行最多 500 字符）。Unity 只汇报总数、最终摘要、失败用例名和有限断言；不得加载逐项成功输出或完整串口日志。已成功的操作不得为报告而重复执行。

### CLI 输出结构与字段提取（必读）

- `loop build`/`flash`/`test-run` 的 JSON 汇总字段（`ok`、`version`、`diqu`、`verification.*`、`updated_readme`、证据路径）打印在标准输出**开头**，其后才跟串口日志行；证据文件（`/d/.../flash-<port>-<timestamp>`、`splc-<port>-<timestamp>`）只保存串口日志，**不含** JSON 汇总字段。
- 禁止用 `tail`/`head`/`sed -n` 等管道截断这些命令的输出——会丢弃开头的 JSON 汇总。也不要为重新抓取字段而重跑已成功的 build/flash。
- 需要结构化字段时，把当次输出重定向到 `/tmp/kilo/` 下的临时文件，再只提取汇总字段：

  ```bash
  python3 -m edbg_pc.cli loop flash --profile cco-hunan --port COM25 > /tmp/kilo/flash-cco-hunan.json 2>&1
  grep -E '"ok"|"version"|"diqu"|"kind"|verification|latest_firmware|updated_readme' /tmp/kilo/flash-cco-hunan.json
  ```

  或从证据文件的串口日志提取 `sversion`/`diqu name` 等文本。退出码与退出状态仍以命令本身为准，重定向不影响。

## 安全约束

- `doctor`、文件检查和串口枚举是只读操作，可以直接执行。
- 构建前确认目标、工程、profile、普通/测试固件类型及实际构建命令。
- 烧录前必须确认精确 COM 口、该端口连接的是目标板，并取得本次烧录授权。历史端口和 profile 默认端口只可作为建议，不能视为授权或硬件事实。
- 不得猜测 CCO 端口；`cco-hunan` 默认值为 `COM11` 时尤其不能使用 `loop run`。
- 串口“可枚举”不等于“可打开”或“属于目标板”。不要自动打开全部候选串口，避免 DTR/RTS 影响板卡。
- 构建失败后立即停止，不得烧录旧产物。烧录失败后先诊断，不得自动重试；再次烧录须重新取得授权。
- 保留并报告 CLI 返回的证据路径。不得用主观描述代替结构化结果。

## 目标与 profile

| 用途 | 工程 | profile | 实际构建命令 |
|---|---|---|---|
| STA 普通固件 | `/home/H_STA/04/sta` | `sta-v2-hunan` | `./bspmake.sh HU_NAN sta_venus2m` |
| STA Unity 测试固件 | `/home/H_STA/04/sta` | `sta-v2-hunan-test` | `make BSPMAKE_OK=1 AREA=HU_NAN_MODE sta_venus2m test-create` |
| CCO 普通固件 | `/home/H_CCO/001/cco` | `cco-hunan` | `make jump` |

优先采用用户明确指定的工程或 profile。若 STA 与 CCO 工程都存在而目标不明确，必须先询问。测试固件仅支持 STA。构建命令由 profile 定义，不要求用户提供 CLI 无法覆盖的任意命令。

## 证据与持久参数

当前证据和设置位于 WSL 原生目录，不得新建 `D:` 证据：

```text
/d/<sta|cco>/<project-name>/
/d/<sta|cco>/<project-name>/readme-<profile-id>.txt
```

对应示例：

```text
/d/sta/04-sta/readme-sta-v2-hunan.txt
/d/sta/04-sta/readme-sta-v2-hunan-test.txt
/d/cco/001-cco/readme-cco-hunan.txt
```

`D:\11-ai-workfile` 仅是旧档案，不自动迁移或删除。

执行前读取当前 profile 的设置，并向用户展示 `project_root`、`profile_id`、`build_command`、`latest_firmware`、`port`、`baud`、`packet_size` 及已有身份字段。保存值只作建议。普通 STA 与测试 STA 不得共享或继承配置；测试 profile 绝不能迁移旧 `readme.txt`。

只有固件传输成功后，运行时才可更新所选 profile。失败的烧录以及独立 `capture`/`grab` 不得更新设置。传输成功后必须核对返回的 `updated_readme.profile_id`、`build_command`、固件路径、端口和身份字段是否与所选 profile 一致；不一致时报告“传输成功但设置同步失败”，不得直接编辑设置文件或未经授权重烧。

## 环境检查与串口发现

```bash
python3 -m edbg_pc.cli loop doctor --profile <PROFILE>
```

已知 `doctor` 会把以 PATH 中 `make` 开头的命令误当成 `<project_root>/make`，导致测试 STA 或 CCO 的 `build_script_exists=false` 假阴性。工程目录存在、`Makefile` 存在且 `command -v make` 成功时，应记录为诊断缺陷，不据此判定无法构建。

Windows 串口需要交叉检查：

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description
Get-PnpDevice -Class Ports -PresentOnly
Get-ItemProperty 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM'
```

`Win32_SerialPort` 可能遗漏 CH340。已确认端口若同时有当前 PnP 与注册表证据，可视为有效枚举证据，但仍须用户确认其板卡角色。

## 构建与烧录

```bash
python3 -m edbg_pc.cli loop build --profile <PROFILE>
python3 -m edbg_pc.cli loop flash --profile <PROFILE> --port <CONFIRMED_DEBUG_PORT>
```

始终显式传入确认过的端口。需要锁定产物时加 `--file /absolute/path/to/firmware.bin`；省略时也必须核对 CLI 选中的绝对路径确属当前 profile。构建成功至少核对并报告：profile、实际命令、`session_dir`、产物绝对路径、大小、SHA-256，以及无关工作树修改。

不要自动使用 `loop run`：它没有 `--port` 参数。只有用户明确确认 profile 默认端口就是目标板端口时才可使用；CCO 应使用分开的 `build` 与显式 `--port` 的 `flash`。

## 烧录后验证

区分“固件传输成功”和“应用身份验证成功”。顶层 `ok=true` 不能替代 `verification` 核查。

普通 STA/CCO 应检查：

```text
version (sversion)
diqu (diqu name)
verification.kind = application_version
verification.ok
evidence
serial_log
readme_path
updated_readme
```

若传输成功但提示符、版本或地区未验证，明确报告“烧录成功，应用验证未完成”，不得声称完整闭环成功。

`sta-v2-hunan-test` 不发送也不要求 `version`，应从启动输出检查：

```text
firmware_identity.hversion
firmware_identity.sver
firmware_identity.isv
verification.kind = test_firmware_identity
verification.ok
verification.missing
evidence
serial_log
readme_path
updated_readme
```

缺字段时如实报告 `verification.missing`，不得额外发送 `version` 补救。

## STA Unity 测试

测试固件构建、烧录并完成身份验证后，使用用户分别确认的调试口和测试输出口：

```bash
python3 -m edbg_pc.cli loop test-run \
  --suite all \
  --debug-port <CONFIRMED_DEBUG_PORT> \
  --port <CONFIRMED_TEST_OUTPUT_PORT>
```

使用 `--suite all`。当前固件启动时调用 `All_tests_main()`；CLI 接受的 `phy`/`dll` 不能可靠筛选用例。分别报告固件身份验证与 Unity 的 tests、failures、ignored、整体状态和 `log_path`，不得互相替代。

## 串口证据采集

已知关键词时优先使用 `grab`：

```bash
python3 -m edbg_pc.cli loop grab '<KEYWORD>' --port <CONFIRMED_PORT> --timeout 120 --context 5 --output <LOG_IN_SELECTED_D_PROJECT_DIR>
python3 -m edbg_pc.cli loop capture --port <CONFIRMED_PORT> --seconds 90 --output <LOG_IN_SELECTED_D_PROJECT_DIR>
```

当前 `grab`、`capture` 和 `test-run` CLI 均无 `--profile` 参数，不得传入。完整原始输出只保存到所选 `/d/...` 工程目录的日志，向 AI 返回匹配附近的有限上下文和证据路径。独立采集不得改写 profile 设置。

## CCO 传输约束

`cco-hunan` 使用 1024-byte X-Modem 包，全程 115200，并在下载前由 profile 发送 `setmode 0`。不要套用 STA 的 128-byte/460800 流程，也不要把某个历史 bootloader 版本写成固定前置条件。兼容性警告可以在后续下载和应用验证成功时记录为 warning；下载失败时只诊断，不自动重试。

### CCO 波特率提升可行性（2026-08-04 实机探测结论，11+ 次实验）

CCO bootloader（Unicorn Bootloader，venus8m）有 `config` 目录和 `setbaudrate` 命令，但实测结论：

- **460800 不可行（直接或两级切换均失败）**：
  - 115200→460800：回显 `baudrate:   460800` 但实际从不切换（460800 下零响应，板卡始终在 115200）。
  - 115200→230400→460800 两级切换：Hop B 从未成功（多轮实验全部失败）。
- **230400 切换本身不可靠**：约 10% 成功率（11+ 次实验中仅 1-2 次真正切换），多数情况 `setbaudrate 230400` 完整回显 `baudrate:   230400` + 提示符但 UART 实际未切换；且 230400 链路上出现字节乱码。疑似 venus8m bootloader 的 setbaudrate 实现不稳定 + COM25 CH341 适配器高速率边缘。
- **结论**：CCO 烧录维持 115200 全程。不要尝试 460800 或 230400 提速，不要相信"先切 230400 再切 460800"的说法（该说法来自 STA venus2m 流程或运行时通用注释，对 CCO venus8m 不成立）。
- 若确实需要提速，方向是：查 venus8m bootloader setbaudrate 源码或更换适配器（STA 的 CP210x 如 COM4/COM24 比 CH341 更可靠），而不是直接改 profile 波特率。
- 探测恢复方法：若板卡停留在 config/非 115200 状态，从实际波特率发 `exit` → `[root /]#` → `reboot` → 本地切 115200 等 `See OS run`/`[node /]$`；找不到提示符时可尝试 DTR/RTS 翻转复位。实测证据见 `/d/cco/001-cco/20260804-141500-baud-probe/` 与 `/d/cco/001-cco/20260804-143000-baud-two-step/`。

## 最终报告

至少报告目标工程/profile/固件类型、实际构建命令与结果、产物路径/大小/SHA-256、确认过的端口、传输结果、身份验证字段、`verification.kind` 与 `verification.ok`、设置同步结果，以及 `session_dir`、`evidence`、`serial_log`、`readme_path` 和 Unity `log_path`。注明是否重试，默认应为“未自动重试”。只有构建、传输、对应身份验证和用户要求的 Unity 测试都有证据通过时，才声明完整闭环成功。