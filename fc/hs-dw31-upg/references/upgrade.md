# 升级海思工程（upgrade）

适用：给海思 DW31 模块做升级包 prepare、commit、查看进度/结果、判定成功/失败、必要时 stop。

**授权口径（2026-11-16 用户定，取代此前"只能网页点"）**：
- **不需要网页点击**。用户在对话中明确说"允许 / 可以烧 / 直接升"即为批准（`contract.md` §3.1 对话级授权）。
- AI 调 `POST /api/upg/commit` 必须带全：`approval_id`、`human_confirmed: true`、`approved_by`（`cli` / `mcp` / `ai`）、`user_approval`（用户原话摘要）。
- 仍禁止：`/api/upg/load`、`/api/upg/start`（绕过门禁）。
- **判定标准以 §7 为准**：`DONE` 不等于升级成功，没拿到"新镜像在跑"的证据就算失败。

## 1. 前置

```bash
CTL="python3 $BASE/scripts/fcctl.py"   # $BASE = hs-dw31-base 技能目录（先读 hs-dw31-base 拿到）
$CTL doctor
```

要求 `data.selected=legacy` 且 `data.legacy.device_ready=true`；否则先按 `references/errors.md` 处理。

### 1.1 包族选择（prepare 前必看，最容易白烧一次的地方）

| 目标产品 | 只能烧这个包 | 说明 |
|---|---|---|
| **融合终端 / ECU（产品类型 501）** | `plc-project/out/sg_fusion_cco/bin/DW31v100_mcore_sg_cco_upg.bin` | `bash scripts/build.sh sg_fusion_cco` 产出，约 458 KB（458,000 / 458,336 B 两个实测值，随 SDK 变化） |
| 国网 CCO | `plc-project/out/sg_cco/bin/DW31v100_mcore_sg_cco_upg.bin` | `sg_cco` 目标 |
| 整包救援（任一） | `out/<target>/image/…_image.fwpkg` | BurnTool + 断电/上电，先停 8765 释放 COM8 |

- **文件名不能当判据**：CCO 与融合终端的在线包都叫 `DW31v100_mcore_sg_cco_upg.bin`，只能看构建目标/目录。
- 烧错族的实测后果：`0x3412/0x3415` 1527/1527 块全部发出，模块回 `upg_status=0xFF`、
  `error_code=0x8007`（`EXT_ERR_BAD_DATA`）、`rcv_file_size=0`，不激活、也不掉线。
- 烧对族（融合包）实测：`rcv_file_size=458000`（=包长）、`error_code=0`、`upg_status=END(验证中)`、
  `0x3419` 后重启、`reconnect_ok=true`、服务 `state=DONE`。
- **路径白名单**：以服务端配置为准（当前是 `C:\fc_diag_client` 与工程 `out/` 整棵，
  见 `contract.md` §3.2）。`prepare` 回 400「路径不在白名单」时，把包复制到
  `C:\fc_diag_client\samples\` 再 prepare，或请维护者把工程 `out/` 加白；不要绕过。

## 2. prepare（只校验，不写 flash）

```bash
$CTL flash-prepare <包路径>          # 例：/mnt/c/fc_diag_client/samples/<包名>_upg.bin
# 包路径必须在服务白名单内（contract.md §3.2）
```

返回：

- `approval_id`、`expires_at`、`human_confirmation_required=true`
- `package.{path,size,sha256,image_count}`
- `target.{port,module_mac,current_version,package_version}`
- `version_diff.same`

注意：

- `prepare` 绝不写 flash；
- `package_version` 目前可能为 `null`，`version_diff.same=false` 不一定代表版本不同（见契约 §6.8）；
- 把 `approval_id` / `package.sha256` / `target` 报给用户。

## 3. 授权与 commit（对话级，AI 可执行）

1. `prepare` 后把 `approval_id`、`package.sha256`、`target.{port,module_mac,current_version}` 报给用户；
2. 用户口头允许后执行（`--user-approval` 填用户原话/摘要，不填会被本地拦下）：

```bash
$CTL flash-commit --approval-id <approval_id> --user-approval "允许" --reset-interval 3
```

3. commit 后立刻轮询 `GET /api/upg/progress`（或 `$CTL flash-status`），不要等请求自己返回；
4. `approval_id` 有效期很短（约 2 分钟），过期就重新 prepare，不要复用；
5. 需要单独复位时用 `$CTL flash-reboot --reset-interval 3`（仅 8765；`--dry-run` 只存延时）。
   服务端仍会独立校验 `human_confirmed`、approval 有效期与包 SHA，见 `contract.md` §3.1。

## 4. 进度/结果

```bash
$CTL flash-status
```

读 `data.summary`（已含激活层字段：`reconnect_ok` / `activation_confirmed` / `last_blk`）：

- `state`：`PREPARED / FLASHING / DONE / FAILED / ABORTED`
- `percent` / `rcv_file_size`：进度
- `upg_status_text`：`OK / END(验证中) / PROCESS / TRANSMIT / FAIL`
- `error_code`：0 为无错误
- `version_after`：完成后版本
- **不要看 `acks`**：固定 0，不代表块 ACK。

成功判定（2026-11-13 修正）：`state == "DONE"` **只代表传输 + 收尾命令已发送，不代表镜像已切换**。

**变体 × 可用升级路径（2026-11-16 实测，先看这张表再动手）**

| 变体 | diag 在线升级（0x3412/0x3415 + 0x3419） | 备注 |
|---|---|---|
| CCO / STA | **可用**（`upg_status` 0→复位，close/reopen 后 `0x3013` 变新） | 本文 §4/§6.4 的结论主要来自这里 |
| **ECU / 融合终端（`scripts/build.sh sg_fusion_cco`）** | **可用（2026-11-16 实测切换成功）** | 传输 OK（1529/1529、`rcv_file_size` 相符、`upg_id`=文件 CRC32）→ `0x3419` 后 **3 秒整重启** → 新镜像运行；判据见 §8.5 |

**定性（2026-11-16 实测更正）**：diag 在线升级在本产品线**是通的**，ECU 变体也一样——`0x3412` 传包 → `0x3410` 查进度 → `0x3411 finish`（可无应答，正常）→ `0x3419 affirm`（提交并复位，`reset_interval` 秒后重启）→ 服务 close/reopen + SRP 重登 → 新镜像在跑。
**注意**：`0x3419` 的"应答"就是重启本身，**没有回包不代表失败**（本项目曾据此误判两次）。切换成功的客观证据见 §8.5。

> **2026-11-13 20:0x 更正（这条最重要，取代此前"diag 不能激活"的结论）**：
> **直接 app 升级（0x3412/0x3415 + 0x3419）已经实测可用，不需要冷上电。**
> 此前"1531/1531 收全、DONE、却从不激活"是**服务端两个 bug**，不是固件限制：
> ① `0x3415` 块头 `file_blk_size` 填 0 → 模块按 0 字节算校验 → 首块即 `0x8000350D (UPG_FILE_CRC_INCORRECT)`、`upg_status=0xFF`；
> ② `0x3410` 状态按 `ext_upg_status_ind_entire` 解析，实际是 `ext_upg_status_ind_s`（60B：`upg_id/blk_size/file_size/num/last_blk_idx/error_code/rcv_file_size/upg_status/mac/upg_end_time`），把 `0xFF` 误读成 0 形成假绿。
> ③ `0x3419 affirm` 后模块按 `reset_interval`（默认 3s）复位，**复位后必须 close() 再 open() + SRP 重登**，否则旧句柄"能写不能收"，表现为 MAK 卡在"升级验证中"。
> 详见 `contract.md` §3.4–§3.5。实测：SPC051 包 1531 块 → `upg_status=1(END)` → 复位 → 重连成功 → `0x3013=SPC051` → `activation.confirmed=true`。

必须再做：

1. 收尾后读 `0x3410`：传输期间 `rcv_file_size` 应等于包大小、`upg_status=0`；finish 后记录可能被清零（`upg_id=0`/`rcv=0`），清零本身不算失败，但也不能当成功。
2. **真实断电上电**（Reset 按钮/BurnTool Reset 不可靠；`0x3009` 也可能不触发），用 `0x5314` 的 `time` 归零确认真重启。
3. 重启后用**唯一运行标记**验证新镜像：`0x3013` 版本串、UART0 波特率/`V9-U0-OK-460800`、或新增信标；只看 `ECU-V9` 无法区分 v9/v10。
4. 三项都对才算成功；`error=None` / `DONE` 单独不算。

## 5. 直接读 0x3410（可选）

```bash
$CTL flash-module-status
```

- 固定发 `0x3410` + 4B param `00000000`（空 param 模块不回复）；
- 应答 60B，解析到 `data.module`：

| 偏移 | 类型 | 字段 | 用法 |
|---|---|---|---|
| 0 | u32 | `upg_id` | 文件 CRC32 |
| 4 | u32 | `blk_size` | 固定 300（**不是** 进度） |
| 8 | u32 | `file_size` | 包总长（**不是** rcv） |
| 12 | u32 | `num` | entry 数，CCO 自升级为 1 |
| 16 | u16 | `last_blk_idx` | 已接收块数（进度看这个） |
| 18 | u16 | `error_code` | 0 = 无错误 |
| 20 | u32 | `rcv_file_size` | 已收字节 |
| 24 | u8 | `upg_status` | 0=OK，1=END，8=UNKNOWN，0xF0=PROCESS，0xFF=FAIL |
| 50 | u8[6] | `mac` | 模块 MAC |
| 56 | u32 | `upg_end_time` | 本轮耗时（秒） |

⚠ 2026-11-13 更正：实际结构是 `ext_upg_status_ind_s`。此前按 `ext_upg_status_ind_entire` 解析（`blk_size` 当 `last_blk_idx`、`file_size` 当 `rcv_file_size`、`num` 当 `blk_size`、`upg_status` 读偏移 20），把 `0xFF(FAIL)` 读成 0，导致"收全、OK、却不激活"的假绿。以本表为准（`contract.md` §3.4）。

`last_blk_idx/blk_size/file_size` 不可用于算进度。

## 6. 实测规则（2026-11-12，2026-11-13 补充）

- **0x3415 没有任何 ACK 帧**：不要等待、不要用 ACK 超时判失败；
- 进度/结果统一用 0x3410；
- 基线：458000/458064 B，1527 块，52~62 s，`rcv_file_size` 等于包大小，
  `upg_status=0`，MAC `00:C9:36:47:58:69`。
- **`affirmed=true` 只表示 0x3419 已发送**，不表示模块接受；`finish_rc=None` 表示 0x3411 无应答。
- **2026-11-13 nomask 对照 + 真实断电**：`FOTA_INFO_AREA Version/Mask=0` 的 v11 包传输 1531/1531、`upg_status=0`、8765 `DONE/error=None`；**真实断电重启**（`0x5314 time` 归零，11:51:33 启动）后仍 `0x3013=SPC050`、业务口 115200 `ECU-V9`、460800 乱码 → **包能收全但不激活**。`DONE`/`error=None` 不能作为升级成功判据。

### 6.1 FOTA_INFO_AREA 版本门槛（2026-11-13）

- `build/config/DW31v100/fota/fota.cfg` 的 `[FOTA_INFO_AREA] Version/VersionMask` 是**升级包的版本兼容门槛**，不是固件版本号；自编译包默认必须保持：
  ```ini
  Version=0x00000000
  VersionMask=0x00000000
  ```
- 设 `VersionMask=0xFFFFFFFF` / `Version=1` 可能让模块在 start 后拒绝或丢弃包；不要用它来“改版本号”。
- 要让 `0x3013` 显示新版本，改 `build/cmake/build_option.cmake` 的 `VERSION`（`DW31_V100R001C00SPC0xx`）并重编；包的 FOTA 字段保持 `0/0`。
- `0x3013` 的版本串来自编译进固件的版本宏，不是 `fota.cfg`；两者不要混。

### 6.2 本地设备升级的提交路径（2026-11-13 代码级，`libplc_upg.a`）

反汇编 `libplc_upg.a:upg_srv_cco_upgrade.c.o`：

- 本地 diag 注册表 `g_cco_upg_local = {0x3410, 0x341D, upg_cco_upg_diag_cmd}`，通过 `uapi_zdiag_register_cmd(instance=0, table, 1)` **只注册了 0x3410–0x341D 这个范围**；
- 该范围内的分发表 `g_upg_cco_cmd` 有：`0x3412/0x3410/0x3413/0x3415/0x341A–0x341D`，**没有 `0x3411`/`0x3419`**；
- 分发表里还有 `0x3660–0x3666`（MDM 状态/传文件/启动/停止/查询），但它们**不在本地 diag 注册范围**内，属于 APP→UPG 的内部消息（`uapi_mdm_upg_msg_send`）；其中 `0x3661` 在库中还是空实现（直接 `return 0`）。

因此：

- COM8 外部 diag 只能发到 `0x3410–0x341D`；`0x3411`/`0x3419` 没有处理函数（`finish_rc=None`），`0x366x` 根本不可达；
- `0x3412/0x3415` 这组 NDM 命令只做“启动 + 传输 + 暂存”，该版本库里看不到 `0x3411/0x3419` 的收尾处理（**但实测模块对 `0x3419` 有反应：复位重启，以实测为准**），也不能从外部 diag 走 `0x3662` 提交；
- 本地提交由内部 UPG 调度器（`upg_controller`/`upg_strategy_*`）完成，完成时 `upg_set_nv_ftm_startup_cfg` 写 NV `0xF05`，重启后由 flashboot 切分区；`upg_device_status_set_nv` 写的是 NV `0xF07` offset 24 的 `device_upg_status`，不是 0xF05 启动标志。

结论（2026-11-18 修订，**取代** 2026-11-16「ECU 变体不成立」那版）：
- 上面这段反汇编只针对当时交付的 SDK 版本 `libplc_upg.a`，是**代码级线索**，不能用来判定某个变体是否支持在线升级；实测已推翻它（见 §4 变体表、`contract.md` §4.2/§7）。
- **CCO/STA**：`0x3412/0x3415` 传完 + `0x3419` → 复位 → 切镜像，实测成立；
- **ECU / 融合终端（`sg_fusion_cco`）**：同样实测可切换（2026-11-16 `0x3419` 后 3 s 重启；2026-11-17 复核 `0x3410` 走位与包族），**不存在"固件缺口、主机侧补不了"**这一说法；
- 凡涉及激活，先查 §4 的变体表与 `contract.md` §4.2；**不要跨变体套用结论，也不要用代码反汇编否定实测结果**。

> 上板三条路，按顺序选：① **直接 app 升级（首选）**：8765 `0x3412/0x3415`（`file_blk_size` 必须填真实长度）+ `0x3419 affirm`，模块 `reset_interval` 后自动复位，**服务 close/reopen 重登即激活，不需要冷上电**（`contract.md` §3.5，实测 SPC051 成功）；
> ② **1376.2 本地 CCO 升级（备选，§6.3）**：946 段 AFN15-F1，模块自动重启，同样不需冷上电，用于 diag 通道不可用时；
> ③ **BurnTool 整包（仅救援/回滚/板子起不来）**：这一步是**物理操作**（断电/上电 + BurnTool GUI），由人执行；它不是网页 commit，服务端不提供整包烧录接口。

### 6.3 1376.2 本地 CCO 升级（产品自带路径，2026-11-13 代码级）

外部 diag 不可用时，走 1376.2 协议本身：

- `AFN12 Fn2` 暂停：帧 `68 0F 00 43 00 00 00 00 00 1E 12 02 00 75 16`，设置 `cco_ctx->pause_flag=TRUE`；
- `AFN15 Fn1` 文件传输：`file_flag=0x03`（`MRS_CCO_LOCAL_CCO_UPGRADE`），`mrs3762_afn15_f1` → `mrs_remote_upg_frame_rx_pro`；
- `mrs_is_cco_state_permit_upg()` 要求 `pause_flag=TRUE` 且不在抄表搜索状态；
- 文件按段写 `uapi_upg_package_storage_write()`，结束帧后 `mrs_upg_local_pro()` → `mrs_remote_upg_start()` → UPG 自己提交。

`content`（从 DT1 开始）偏移：

| 偏移 | 字段 |
|---|---|
| 0–1 | DT1/DT2（AFN15 Fn1 → `01 00`） |
| 2 | `file_flag=0x03` |
| 3 | `file_property`（0=数据帧，1=结束帧） |
| 4 | 保留 0 |
| 5–6 | `total_seg_num` u16 LE |
| 7–10 | `curr_seg_num` u32 LE |
| 11–12 | `data_len` u16 LE |
| 13… | 文件数据 |

### 6.3.1 实测结论：这条路已跑通，**不需要冷上电**（2026-11-13 16:38）

- 实测 SPC054 → **SPC055**：AFN12-F2 暂停 + AFN15-F1 发 **946 段**，**946/946 段 4 B ACK 等于 seg_id**，
  `0x3410` 读数 `upg_id=1 / rcv_file_size=459312 / upg_status=0`，模块 **16:38:54 自动重启**
  （`0x5314 time` 1,888,020→188,040 ms），重连串口后 `0x3013` 读回 **SPC055**。
- 因此**日常上板不需要 BurnTool、不需要物理断电**；BurnTool 整包只在救援/回滚/板子起不来时用（那个才要冷上电）。

### 6.3.2 硬约束：单帧上限 512 字节（超了静默丢弃）

- 实测（裸串口 115200 8E1，AFN15-F1）：整帧 **512 B 收、513 B 丢**，丢弃时**没有任何否认帧**，只当超时。
- AFN15-F1 帧开销固定 **26 B**（`68` + `L`×2 + `C` + 6 B `R` + `AFN` + `DT`×2 + 升级头 11 B + `CS` + `16`），
  故**单段数据上限 = 486 B**。
- 459,312 B 的包 → **946 段**（945×486 + 尾段 42 B）。历史「449 段零响应」就是旧脚本 `SEG_LEN=1024`（每帧约 1050 B）全部超限被丢。

### 6.3.3 每段判据与失败形态

- 每段应答 = 4 B「收到当前段标识」（u32 LE），应等于该段 `seg_num`；`0xFFFFFFFF` = 错误（代码口径，标准卡写 `0xFFFFH`）。
- 末段 `file_property=1`（结束帧），`data_len` 允许短于 486。
- **零应答**只有两种解释：①整帧 > 512 B 被链路层丢；②板子应用侧停摆（信标照打但协议/诊断都不答，需**冷上电一次**才恢复）。**不是帧格式错**。
- 升级完成后必须**关闭并重开串口会话**再读 `0x3013`；8765 `/api/version` 是缓存，旧会话会一直显示老版本（见 `contract.md` §3.5）。

### 6.4 直接 app 升级（diag 通道）三个必守点（2026-11-13 实测，`contract.md` §3）

1. **`0x3415` 块头 12B 必须完整正确**：
   ```
   u16 check_sum      = sum(本块数据字节) & 0xFFFF
   u16 file_blk_size  = 本块真实数据长度（300；末块为余数）
   u32 upg_id
   u16 req_sn         = idx-1
   u16 idx            = 1 起
   u8  data[...]
   ```
   `file_blk_size` 填 0 → 首块即 `0x8000350D UPG_FILE_CRC_INCORRECT`、`upg_status=0xFF`、后续永不激活。**成功块没有逐块 ACK**（静默），`last_blk_idx` 递增才是进度。
2. **`0x3410` 按 §5 的真实偏移解析**（`upg_status` 在偏移 24；`contract.md` §3.4 是同一张表）。
3. **`0x3419 affirm {upg_id, reset_interval, option}` 后必须 close/reopen 串口**：模块 `reset_interval`（默认 3s，0–3600）后复位，旧句柄"能写不能收"，只在旧句柄上重试 SRP 会一直失败（MAK 卡"升级验证中"）。服务侧发 0x3419 后立即 close，等 `max(2, reset_interval+2)` 秒再 open + SRP 重登；WSL 侧不要自行开串口。
4. 相关接口：`POST /api/upg/commit`（可带 `reset_interval`）、`POST /api/upg/reboot`（发 0x3419，`dry_run` 只存默认值）、`GET /api/upg/progress` 的 `progress.last_blk` / `reboot.reconnect_ok` / `activation.confirmed`。
   `activation.confirmed=true` 的判据：`0x3013` 版本串包含目标 `SPCxxx` 且该版本烧录前不存在；同版本重刷保持 `null`。


### 6.5 停止烧录

```bash
$CTL flash-stop --force
```

- 只在用户明确要求时；
- 8765 需要 `--force`；stop 是安全动作，但不要自动调用。

## 7. 升级成功/失败硬判据（2026-11-16 用户要求：不许"成功与否不知道"）

两层都过才算成功；**任一层缺证据 = 失败**。

### 7.1 传输层（必须全中）
- `GET /api/upg/progress`：`progress.sent == progress.total`（100%）；
- `module.rcv_file_size` == 升级包字节数；
- `module.upg_id` == `zlib.crc32(包)`；
- `module.error_code == 0`；
- `module.upg_status` ∈ {0(OK), 1(END)}；`0xFF` 或其他值一律判失败；
- ⚠ `progress.acks` 固定 0，**不要看**。

### 7.2 激活层（必须拿到"新镜像在跑"的证据）
按变体各有一条唯一运行标记，缺一不可：
- **CCO/STA**：`0x3013` 版本串含目标 `SPCxxx`（烧录前不存在）且 `progress.reboot.reconnect_ok == true`；
- **ECU / 融合终端（`sg_fusion_cco`）**：管理口 `link` 必须回 `0x81` 且型号串与本次构建一致（当前 `B1D0X-F`），且**旧镜像特征必须消失**（历史特征：`68 37 00 80 03 …` 的 EC000310 应答、`ECU-PING` 裸写串）。
- 复位证据三取一：`reconnect_ok == true`；串口 close/reopen + SRP 重登后版本/行为变了；`0x3013` 读取前后出现重启间隙。
- **首选做法是 §8.4 的"唯一运行标记法"**：ECU 变体的 `0x3013` 取的是 NV 值，不随编译变，靠它判不出新镜像。

### 7.3 失败兜底（按顺序）
1. `upg_status=1 END` 但 7.2 不成立 → 判"**传输成功、未激活**"，转 §6.3 1376.2 路径（实测能自动重启切镜像）；
2. 1376.2 段 ACK 异常 → 先查 `data_len` / `file_blk_size` 与单帧 512 B 上限（§6.3.2），**不要换包试**；
3. **禁止**用"手工写 NV `0xF05` + 重启"这类兜底（曾用自定义命令 `0x531E`）——flashboot 不认，实测会把板子带进失联状态（见 §8.1）；
4. 都失败 → BurnTool 整包（救援/回滚专用），并记录"该变体 diag 路径不可用"。

### 7.4 回执模板（缺项视为没做）
```
变体：sg_cco | sg_fusion_cco
包：<文件名> <字节数> sha256=<...>
prepare：approval_id=<...> expires_at=<...>
授权：user_approval="<用户原话>"
传输：sent/total=<...> rcv=<...> upg_id=<...>（vs crc32 <...>）upg_status=<...> error_code=<...>
激活：reconnect_ok=<...> 唯一标记实测=<...> 旧特征消失=<是/否>
结论：PASS | 传输成功未激活 | FAIL（原因）
```

### 7.5 烧录 ≠ 全部：宿主侧 DB 必须同步（2026-11-18 实测补充）

**烧录包只带镜像，不带解析用的 XML/DB。** 新增了 NV 项或改了日志格式的固件，烧完必须同步宿主侧 DB，否则"看得见值、认不出东西"。

| 现象 | 真因 | 处置 |
|---|---|---|
| `nv-read` 返回 `rc=0` 但 `item=null`/`decoded=null` | 宿主 NV 目录缺该 key | 见下"同步步骤" |
| `nv-list` 项数与固件不符（新增项查不到） | 同上 | 同上 |
| 自己打的字符串日志在 `/api/logs`、帧日志里都搜不到 | 该日志走模块文件日志通道，**不进 8765 帧通道** | 不要靠帧日志验证；改用可读回的状态（NV/DIAG 查询） |

**同步步骤**（宿主侧要拿到本次构建 `system/` 下的）：

```text
hdbcfg/mss_prim_db.xml          prim 库
hdbcfg/mss_nvi_db.xml           NV 目录
diag/*_msg_struct_def.txt       结构定义
nv/nv_app_struct_def.txt        NV 结构
```

1. prim 库热加载：`POST /api/prim/reload {path}`（路径须在白名单内，UNC 转换）；
2. **NV 目录 `prim/reload` 不重载** —— 必须重启诊断服务：8766 控制面 `POST /api/v1/services/diag/stop` → `/diag/start`（见 `contract.md` §2.1）；
3. 重启后 `doctor` 等 `device_ready=true`，再验证 `nv-list` 项数与 `nv-read` 的 `item` 是否非空。

**真正的坑（2026-11-18 实测，修正此前"生成链漏项"的误判）**：`mss_nvi_db.xml` 其实**正常生成**了该项（里面的 `ID` 是**十进制**，如 `ID="1108"` = `0x454`，用十六进制 grep 会误判）。8765 显示 NV 用的是宿主两份产物：`data/nv_catalog.json`（项目录，用 `make_nv_catalog.py <固件 mcore_default.json>` 生成）与 `data/nv_structs.etypes`（结构体布局，取自构建产物 `out/DW31v100/build/database.etypes`）。这两样**没有 HTTP 上传接口**（`prim/reload` 只管 prim），同步后必须用 8766 接口 `diag/stop`→`diag/start` 重启才生效。否则设备能读，上位机显示 96 项、`item=null`。

## 8. 反模式与误判（2026-11-16 实测教训）

### 8.1 禁止：手工写 NV `0xF05` 当"提交"
- 做法：自建 diag 命令写 `ext_nv_ftm_startup_cfg{status=1, load_flash_addr, rcv_file_size, upg_id, last_blk_idx}` 再 `uapi_reboot_system`。
- 后果：**flashboot 不认手工写的启动标志**；load 地址猜错会把板子带进失联（两路串口全静默、8765 diag `ack=null`），只能 BurnTool 整包救援。本项目用 `0x531E` 干过一次，板子当场起不来。
- 结论：`0xF05` 只允许 **UPG 自己**写。

### 8.2 若必须给固件补"收尾"，正确接法
- 接进 UPG 的 commit 状态机：`mrs_upg_local_pro()` → `mrs_remote_upg_start()` → `uapi_mdm_upg_msg_send(EXT_MDM_UPG_START, ...)`；
- 或走 UPG 自带 affirm 通道（`uapi_mdm_register_affirm_notify` / `upg_affirm_*`），**不要自己写 NV**；
- 重启不要挂在可能停摆的业务任务轮询上（用独立定时器或 diag 上下文延时重启）；
- 状态缓存无效时不要用 `rcv=0/last=0` 凑数，也不要静默返回，要回明确错误码。

### 8.3 误判清单（本项目踩过）
| 现象 | 错误归因 | 正确判据 |
|---|---|---|
| 全 ACK + `upg_status=1(END)` 就以为快好了 | 把传输当激活 | END 只是"收齐待验证"，激活看 §7.2 |
| `0x3419` 发出无反应 → 认为"命令没注册" | 用空参数探针判注册 | 空参数任何命令都不回（`0x3410` 已验证），必须带合法参数 |
| 拿 CCO/STA 的 diag 结论套到 ECU | 没看变体表 | 先看 §4 变体 × 路径表 |
| 模块不答还继续发升级/兜底命令 | 把"任务停摆"当"命令没生效" | 协议+诊断都不答而信标照打 = **冷上电**，停止一切命令 |
| 只看 `0x3013` 判是否升级成功 | ECU 该值取自 NV，不随编译变 | 用 §8.4 唯一运行标记法 |

### 8.4 唯一运行标记法（推荐）
1. 临时给固件加打印：每 N 秒往**管理口**裸写一行 `ECU_<TAG>`（不组帧，便于裸读）；
2. 编两版：在板那版一个标记、目标版另一个标记；
3. **编完立刻撤补丁**，产品仓不留脚手架，补丁原文存文本备查；
4. 判据：升级后**新标记出现、旧标记消失**；只剩旧标记 = 未切镜像。

### 8.5 判断"镜像是否真切换"的两条硬证据（2026-11-16 实测）
1. **NV `0xF05`（`tfm_cfg_id`，`ext_nv_ftm_startup_cfg`，40B）**：切换生效后为 `status=1` + `load_flash_addr=0xFE000` + `upg_id` = 该升级包的 CRC32。可用 `POST /api/nv/read {"nv_id":3845}` 直接读回。**这是程序性证据，不依赖业务代码是否正常。**
2. **运行标记法（§8.4）**：目标包编入周期性打印（如 `ECU_<TAG>`），升级后应看到新标记、旧标记消失。

⚠ 两个坑：
- 新镜像**业务任务可能起不来**（本次 V2 构建即如此：标记不打、698 不答），此时**不能**据此判"没切换"——先看 NV `0xF05` 的 `upg_id` 对不对。
- 手工清 NV `0xF05`（写 40B 全 0）可以解锁"卡在脏标志"的板子，但**不要手工写 status=1**（那是 §8.1 的禁令）。

## 9. 错误

| code | 含义 | 处置 |
|---|---|---|
| `LEGACY_PREPARE_MISSING` | 8765 旧版没有 prepare | 让 Windows 侧按契约 §3.6 补齐；不要退回旧 start |
| `FLASH_NOT_PREPARED` / `FLASH_APPROVAL_EXPIRED` / `FLASH_PACKAGE_CHANGED` | approval 无效/过期/包变了 | 重新 prepare；不要绕过 |
| `FLASH_IN_PROGRESS` | 已有烧录 | 等 status 或让用户处理 |
| `NOT_LOGGED_IN` / `COM_RELEASED` | 会话/端口不可用 | 按 `references/errors.md` |
| `HUMAN_CONFIRM_REQUIRED` | commit 没带 `human_confirmed:true` | 用 `flash-commit`（自动带 true），不要手拼 HTTP |
| `USER_APPROVAL_REQUIRED` | 缺 `user_approval` | 先取得用户明确允许，再填原话/摘要 |
