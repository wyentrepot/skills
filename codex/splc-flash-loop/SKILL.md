---
name: splc-flash-loop
description: 构建、烧录并验证 SPLC STA/CCO V2 固件，使用现有 EDBG 闭环工具保存工程级证据和按 profile 隔离的持久参数。适用于 STA venus2m、CCO venus8m、版本与地区验证、串口证据采集、环境诊断及 STA Unity 测试。
---

# SPLC STA/CCO V2 实机闭环

本文件是此技能的权威说明。`QUICKSTART.md` 和 `INSTALL.md` 是旧资料；若与本文件或当前 CLI 不一致，以本文件和当前运行时为准。

## 运行时与输出控制

在 WSL 中使用现有运行时：

```bash
cd /home/ai_work/splc_tool/edbg_pc_debug_tool_full_source
python3 -m edbg_pc.cli loop --help
```

构建、Unity 和长时间串口输出必须重定向到所选工程的 `/d/...` 证据目录，不要把完整日志载入 AI 上下文，也不要使用 `tee`。成功时只返回退出码、耗时、必要结果字段、产物及证据路径；失败时只展开首个根因附近的有限上下文（默认最多 80 行、每行最多 500 字符）。Unity 只汇报总数、最终摘要、失败用例名和有限断言；不得加载逐项成功输出或完整串口日志。已成功的操作不得为报告而重复执行。

## 安全约束

- `doctor`、文件检查和串口枚举是只读操作，可以直接执行。
- 构建前确认目标、工程、profile、普通/测试固件类型及实际构建命令。若有 readme 有效记录且用户确认复用参数（见"参数复用"），readme 的全部字段视为已授权，跳过逐项确认。
- 烧录前必须确认精确 COM 口、该端口连接的是目标板，并取得本次烧录授权。复用流程中 readme 记录的端口视为用户已授权。
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
/d/<sta|cco>/<project-name>/                     ← readme 持久设置
/d/<sta|cco>/<project-name>/<YYYYMMDD-HHMMSS>/   ← 每次烧录的时间戳文件夹
```

所有日志文件无后缀名：

```text
/d/sta/04-sta/readme-sta-v2-hunan                ← 持久设置（下次烧录读取）
/d/sta/04-sta/20260729-090200/                   ← 本次烧录证据
/d/sta/04-sta/20260729-090200/flash-COM23-20260729-090200
/d/sta/04-sta/20260729-090200/splc-COM23-20260729-090200
/d/sta/04-sta/20260729-090200/readme-sta-v2-hunan
```

`D:\11-ai-workfile` 仅是旧档案，不自动迁移或删除。日志实际落盘到 `/d/<sta|cco>/<project-label>/<YYYYMMDD-HHMMSS>/` 时间戳子文件夹，由 `loop_orchestrator.py:_archive_worker_outputs` 在烧录完成后自动归档。

执行前读取当前 profile 的 readme 设置。若 readme 存在且为最近一次成功烧录（见"参数复用"），**直接视为有效授权，无需重新确认**，向用户展示并给出一键确认即可。

每次固件传输成功后，运行时自动将以下参数写回 readme：
- `profile_id`、`project_root`、`build_command`、`port`、`baud`、`packet_size`
- 普通固件：`last_version`、`last_diqu`
- 测试固件：`last_hversion`、`last_sver`、`last_isv`
- `last_flash`（时间戳）
- `firmware_type`（`normal` 或 `test`）

普通 STA 与测试 STA 的 readme 按 profile 隔离（`readme-sta-v2-hunan` vs `readme-sta-v2-hunan-test`），互不继承。传输成功后必须核对返回的 `updated_readme.profile_id`、`build_command`、固件路径、端口是否与所选 profile 一致；不一致时报告"传输成功但设置同步失败"，不得直接编辑设置文件或未经授权重烧。

## 参数复用

readme 在每次成功烧录后自动更新，保存了全套已验证的参数。新 session 开始时，AI 应：

1. 读取对应 profile 的 readme（路径见"证据与持久参数"）
2. 若 readme 存在且包含 `last_flash` 字段（表明上次成功烧录过），readme 中的参数**视为已验证的有效授权**
3. 向用户展示全部已有字段，**给出一键"复用全部参数？"确认**，无需逐项询问

问答模板：

```
检测到上次烧录记录：
  profile: sta-v2-hunan
  工程路径: /home/H_STA/04/sta
  编译命令: ./bspmake.sh HU_NAN sta_venus2m
  固件类型: 普通固件
  端口: COM23
  上次版本: sversion:004303

本次操作是否完全复用以上参数？[是/否]
```
- **是** → 跳过安全约束中的逐项确认，直接编译烧录。普通固件用 `loop run --port <port>`，测试固件执行 `make clean + 测试固件编译 + loop flash`
- **否** → 回到安全约束的逐项确认流程

复用条件：同 profile + 同固件类型（`firmware_type` 字段一致）。若此次需要切换到测试固件或不同 profile，不得复用，必须逐项确认。

## 环境检查与串口发现

```bash
python3 -m edbg_pc.cli loop doctor --profile <PROFILE>
```

`doctor` 必须区分 PATH 命令和相对脚本：`make` 等裸命令通过 PATH 检查，含路径分隔符的命令才相对工程目录检查。返回项使用 `build_command_available`；失败时按真实检查结果处理，不再接受 `<project_root>/make` 假阴性。

Windows 串口需要交叉检查：

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description
Get-PnpDevice -Class Ports -PresentOnly
Get-ItemProperty 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM'
```

`Win32_SerialPort` 可能遗漏 CH340。已确认端口若同时有当前 PnP 与注册表证据，可视为有效枚举证据，但仍须用户确认其板卡角色。

## 构建与烧录

每次编译前必须 clean：

```bash
make clean
python3 -m edbg_pc.cli loop build --profile <PROFILE>
python3 -m edbg_pc.cli loop flash --profile <PROFILE> --port <CONFIRMED_DEBUG_PORT>
```

构建失败时优先读取结构化字段 `first_error`、`build_log` 和不超过 80 行的 `error_context`。不要把完整构建日志重新送入上下文；需要深挖时围绕 `first_error` 在 `build_log` 中做定点检索。

输出必须把 `profile_id` 与地区分开：构建前使用 `configured_region`，烧录验证后使用 `actual_region`（兼容旧字段 `diqu`）。profile 名称只是工具配置标识，不能作为固件地区结论。

测试固件在 clean 后执行 `make BSPMAKE_OK=1 AREA=HU_NAN_MODE sta_venus2m test-create`。

复用参数时直接用 readme 中的端口调用 `loop run --port <readme_port>` 或 `loop flash --port <readme_port>`，无需重新确认。需要锁定产物时加 `--file /absolute/path/to/firmware.bin`；省略时也必须核对 CLI 选中的绝对路径确属当前 profile。

`loop run` 已支持 `--port <PORT>` 覆盖 profile 默认端口，可直接使用：

```bash
python3 -m edbg_pc.cli loop run --profile sta-v2-hunan --port COM23
```

参数复用成功后，AI 可直接用 readme 中的端口调用 `loop run --port <readme记录的端口>`，无需拆 build + flash 两步。

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
readme_snapshot
updated_readme
```

`readme_path` 指向 `/d/<sta|cco>/<project-name>/readme-<profile>` 的固定持久文件；`readme_snapshot` 指向本次时间戳证据目录中的只读快照。下一次复用只读取固定持久文件。

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

## 日志修改验证

若本次烧录涉及源代码 log 变更，烧录后必须额外执行日志验证闭环：

1. **捕获方式**：烧录后打开同一串口，发送触发命令（如 `vermgmt bin`），等待并采集完整输出
2. **验证关键字**：确认捕获输出中包含预期的 log 前缀或内容
3. **修复捕获不完整问题**：若 `loop flash` 内置验证输出的 `VERIFY] version output` 被截断（如只显示 2-8 行），是因为 `loop_worker.py` 中发送 `version` 后仅单次 `ser.read_available()`，未循环等待所有输出。修正方式为改用循环持续读取直到稳定静默期（1.5s 无数据）或出现 shell 提示符
4. **证据落盘**：所有捕获原始日志写入当前烧录的时间戳文件夹 `/d/<sta|cco>/<project-label>/<YYYYMMDD-HHMMSS>/`，向 AI 返回匹配行附近的有限上下文和证据路径
5. **证据文件加密/损坏排查**：若旧路径 `/d/sta/04-sta/splc-*` 出现 SafeNet/LOCK 二进制数据，系 `/d/` 挂载路径被 Windows 搜索索引或防病毒软件写入干扰。改用时间戳子文件夹后文件名不再固定，已避免此冲突

## 指令下发与抓取

`loop grab` 和 `loop capture` 只能被动听串口输出，不能主动发命令。若待验证的 log 需要通过 CLI 命令触发（如 `vermgmt bin` 才印 `[assoc]`，或 `version` 才印版本），使用此工具：

### 工具位置

```bash
/root/.config/kilo/skills/splc-flash-loop/tools/send_cmd_and_grab.py
```

### 使用方式

```bash
# 发命令 + 等关键字 (最常用)
python3 /root/.config/kilo/skills/splc-flash-loop/tools/send_cmd_and_grab.py \
  --port COM23 --cmd "vermgmt bin" --keyword "[assoc]" --timeout 20

# 只发 version 等自动出现的输出
python3 /root/.config/kilo/skills/splc-flash-loop/tools/send_cmd_and_grab.py \
  --port COM23 --cmd "version" --keyword "sversion"

# 只收不发 (等效 loop grab，但带 --cmd 时等价于 send + grab)
python3 /root/.config/kilo/skills/splc-flash-loop/tools/send_cmd_and_grab.py \
  --port COM23 --keyword "sta main task" --timeout 120

# 传 --type 自动按 /d/<type>/<project>/<timestamp>/ 格式生成证据路径
python3 /root/.config/kilo/skills/splc-flash-loop/tools/send_cmd_and_grab.py \
  --port COM23 --cmd "vermgmt bin" --keyword "[assoc]" --type sta

# 指定证据路径（手动）
python3 /root/.config/kilo/skills/splc-flash-loop/tools/send_cmd_and_grab.py \
  --port COM23 --cmd "vermgmt bin" --keyword "[assoc]" \
  --output /d/sta/04-sta/20260729-094200/assoc-evidence.log
```

### 原理

该脚本将待执行的 Python 代码（内含 `SerialBackend` 操作）写入临时文件，通过 `wslpath -w` 转为 Windows UNC 路径，用 `powershell.exe` 调用 Windows 侧 Python 执行。Windows 侧的 pyserial 直接操作 COM 口，实现 WSL → PowerShell → Windows Python → 串口的完整链路。

### 返回值

成功时输出 JSON：
```json
{
    "ok": true,
    "keyword": "[assoc]",
    "matched": true,
    "context": ["...", "[assoc] network_optimize:1", "..."],
    "total_lines": 173,
    "evidence_path": "/tmp/kilo/splc-evidence/COM23-20260729-094200"
}
```

- `ok`: 关键字是否匹配到
- `context`: 匹配行前后各 5 行（默认），供 AI 使用
- `evidence_path`: 全量原始日志路径（不指定 `--output` 时，传 `--type`则自动按 `/d/<type>/<project>/<timestamp>/` 生成，否则落到 `/tmp/kilo/splc-evidence/`）
- AI 只处理 `context`，不需要读取全量文件

### 与 `loop grab` 的对比

| 特性 | `loop grab` | `send_cmd_and_grab.py` |
|------|-------------|------------------------|
| 被动听串口 | ✅ | ✅ |
| 主动发命令 | ❌ | ✅ (`--cmd`) |
| 等关键字 | ✅ | ✅ |
| 返回上下文 | ✅ | ✅ |
| 证据落盘 | ✅ (到 `/d/...` 时间戳目录) | ✅ (`--output` 指定或 `--type` 自动生成) |
| 超时 | 120s 默认 | 20s 默认 |
| 目标类型推断 | ❌ (需手动 `--port`) | ✅ (`--type sta|cco` 自动生成证据路径) |

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

## 最终报告

工具已返回结构化 JSON（含 `ok`、`verification`、`evidence`、`serial_log` 等），AI **不要重复叙述 JSON 中已有的字段**。报告只需包含：

1. **结论**：成功 / 失败（哪个阶段失败）
2. **异常项**（如有）：`verification.ok=false` 时报告缺了什么字段；设置同步不一致时报告
3. **证据路径**：`evidence`、`serial_log`、`session_dir`
4. **是否重试**：默认为"未自动重试"

示例（成功时）：
```
HU_NAN STA 普通固件编译烧录完成。
  传输: 成功
  验证: sversion=004303, diqu=湖南
  证据: /d/sta/04-sta/20260729-094200/
  未自动重试
```

示例（失败时）：
```
HU_NAN STA 编译失败 (exit code 2)。
  make/objects/sta_venus2m/xxx.o 报错: xxx
  日志: /d/sta/04-sta/20260729-094200/flash-COM23-...
  未自动重试
```

只有构建、传输、对应身份验证和用户要求的 Unity 测试都有证据通过时，才声明完整闭环成功。
