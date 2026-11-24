# 服务与烧录契约（contract）

> 本文件是 hs-dw31 技能内**唯一权威**：Windows FC 服务（8765）的对外行为、烧录门禁、`0x3410` 布局、成功判据、字段与禁止项。
> 技能外文档（如 FC 服务仓库的 `docs/WINDOWS_CONTRACT.md`、`docs/AI_CONTROL.md`）只作历史背景；冲突以本文件为准，并把差异补回这里。

## 1. 服务与传输

- **主后端**：Windows `127.0.0.1:8765`（`fc_service.py`，单服务）。8770/8780 是历史/可选，不要求。
- WSL 直连 Windows 回环会 `Connection refused`；CLI 默认 `--transport auto`，自动改用 Windows `curl.exe`（`/mnt/c/Windows/System32/curl.exe`）。可用 `--transport direct|wincurl` 强制。
- 传输：HTTP/1.1 + JSON，UTF-8；时间用本地 ISO `YYYY-MM-DDTHH:MM:SS`，帧内 `ts` 为 `HH:MM:SS.mmm`。
- 响应：成功 `{"ok":true,...}`；失败 `{"ok":false,"error":{"code","message","detail"?}}`（旧版字符串 error 也兼容）。

HTTP 码：

| code | HTTP | 含义 |
|---|---|---|
| `BAD_REQUEST` | 400 | 参数/JSON/包路径/包内容错误 |
| `NOT_FOUND` | 404 | 路径/资源不存在 |
| `NOT_LOGGED_IN` | 409 | 会话未登录 |
| `SESSION_MUTED` | 409 | 心跳超时，模块静默，需断电 |
| `COM_RELEASED` | 409 | 端口已让出（Start.exe/MaintenanceKits） |
| `FLASH_NOT_PREPARED` | 409 | 无有效 approval / 已用 / 不匹配 |
| `FLASH_APPROVAL_EXPIRED` | 409 | approval 过期（TTL 120 s） |
| `FLASH_PACKAGE_CHANGED` | 409 | 包内容与 prepare 时不一致 |
| `FLASH_IN_PROGRESS` | 409 | 已有烧录任务 |
| `HUMAN_CONFIRM_REQUIRED` | 400 | commit 缺 `human_confirmed:true` |
| `USER_APPROVAL_REQUIRED` | 400 | AI/CLI commit 缺 `user_approval` |
| `NV_READ_FAILED` / `NV_WRITE_FAILED` | 502 | NV 失败 / 回读不一致 |
| `INTERNAL_ERROR` | 500 | 服务内部错误 |

并发与超时：

- 所有设备命令**串行**（`send`、`nv/*`、`topo`、`upg/*` 共用一把锁）；`state/frames/logs/prim/nv items/upg progress` 只读缓存，不占锁，应 <1 s 返回。
- 建议超时：state/version/frames/logs/prim/nv items 2 s；topo 5 s；send / nv rw 5 s；prepare 60 s；progress 1 s（轮询）。
- 烧录期间只允许查进度和 stop；其他设备命令排队或 409，不要并发发帧。

## 2. 端点（技能会用到的全部）

| 方法 路径 | 要点 |
|---|---|
| `GET /health` | `{ok,service,version,protocol}`；存活探测首选 |
| `GET /api/state` | `port,baud,logged_in,port_open,start_running,mode,module_ver,error,rx,tx,reconnect_count,last_reconnect,prim{path,count},biz{dir},logfile` |
| `GET /api/version` | `module_ver`（可能是缓存，升级后要 close/reopen 再读） |
| `POST /api/relogin` | 空 body；Start.exe 退出后重新登录 |
| `GET /api/frames?since&limit` | 原始帧（最新 limit 条，limit≤2000）；`last_id` 续拉 |
| `GET /api/logs?since&limit` | 仅日志类帧 `0x5304/0x5314/0x5315/0x5316` |
| `GET /api/prim/logs?since&limit` | prim 解析行：`id,ts,category,no,tick,prim_id,prim_hex,prim_name,structure,source_hex,dest_hex,data_len,has_struct` |
| `GET /api/prim/frame?id=` | prim 结构树 `{row,data_hex,tree,note}`；`note` 非空说明布局与长度不符，**不要硬解** |
| `GET /api/dev/topo?timeout=` | `entries[]`：`mac,tei,proxy_tei,level,ability,role,product,online,phase_text,spc_ver,sw_ver,b_ver,version_time` |
| `GET /api/nv/items?module&q&cco&limit` | NV 目录 `key_id,key_hex,name,module,structure,status,cco` |
| `POST /api/nv/read {nv_id,wait}` | `rc,rc_text,crc,crc_ok,data_hex,data_size,decoded` |
| `POST /api/nv/write {nv_id,data_hex,confirm,verify}` | 缺 `confirm:true` 必须拒绝；`verify.match` 要 true |
| `POST /api/send {cmd_id,param_hex,secure,wait}` | 返 `ack` 帧 + `decoded`；`cmd_id` 接受 `0x3013` / 十进制 |
| `POST /api/upg/prepare {package_path}` | 只校验不写 flash，见 §3 |
| `POST /api/upg/commit {approval_id,human_confirmed,approved_by,user_approval,reset_interval?}` | 见 §3 |
| `GET /api/upg/progress` | 见 §3.4 |
| `POST /api/upg/stop` | 任意阶段可停；8765 侧 CLI 需 `--force` |
| `POST /api/upg/reboot {reset_interval?,upg_id?,option?,dry_run?}` | 单独发 `0x3419`；`dry_run:true` 只存延时 |
| `POST /api/prim/reload {path|xml_hex}` | 热加载 prim 库，路径转 UNC 并持久化 |

> MCP 薄层（`win_service/mcp_stdio.py`，若部署了）能力与本表一致；其中 `fc_upgrade_commit` 只在用户明确授权后调用、必须带 `user_approval`，CLI 等价命令为 `flash-commit`。

### 2.1 控制面（8766，`wsl-control`）—— 让端口 / 重启 8765

**8765 自身没有"重启服务"接口**（`/api/services`、`/api/service/restart` 均 404）。服务管理在**独立控制面 8766**（实测 `wsl-control 2.0.0`）：

| 方法 路径（8766） | 作用 |
|---|---|
| `GET /api/v1/services` | `bridge{windows,wsl}`、`gateway`、`diag.health{service,version}` 健康 |
| `GET /api/v1/ports` | 各业务端口（simcon/simeter 等）的 com/baud/bridge 状态 |
| `POST /api/v1/services/diag/stop` | **释放 COM8**（BurnTool 整包前必用，取代"手工停 Start.exe"） |
| `POST /api/v1/services/diag/start` | **重启 8765 诊断服务** |

```bash
CURL=/mnt/c/Windows/System32/curl.exe
"$CURL" -s -X POST http://127.0.0.1:8766/api/v1/services/diag/stop
"$CURL" -s -X POST http://127.0.0.1:8766/api/v1/services/diag/start
```

规则：

- **没有 `/api/v1/services/diag/restart`**（404）；"重启"= `stop` 后再 `start`；
- `start` 返回后要等 `doctor` 的 `device_ready=true` / `status.logged_in=true` 再发设备命令；
- `diag/stop` 会让 8765 不可达（`NO_BACKEND`），属预期，不要据此判服务坏；
- **凡改了固件的 NV 项/日志 prim，宿主侧必须重新加载 DB**：`/api/prim/reload` **只重载 prim，不重载 NV 目录**；NV 目录要 `diag/stop` + `diag/start` 才会重新读（见 §2.2）。

### 2.2 固件 ≠ 全部：宿主侧 DB 必须同步

镜像只带代码；**NV 项名/结构、日志 prim 定义都在宿主侧的 XML/DB 里**。烧录新固件（尤其新增了 NV 项或日志格式）后，若不换宿主 DB：

| 现象 | 真实原因 |
|---|---|
| `nv-read` 返回 `rc=0` 但 `item=null`、`decoded=null` | 宿主 NV 目录没有该 key（不是 NV 写坏） |
| `nv-list` 项数与固件不符（如新增项查不到） | 同上，需重新加载 NV 目录 |
| 自己打的日志 `0x5314` 里根本没有该 msg_id | **设备侧上报开关没开该 module_id**（`0x5310`），记录压根没上串口 |
| `0x5314` 里有该 msg_id，但显示 `[0x..] (未知 msg_id)` | 宿主 prim 库没有这个 id（id 未随构建生成，或改过 id 没 `prim/reload`） |

需要跟进的产物位于构建输出的 `system/` 下：`hdbcfg/mss_prim_db.xml`（prim 库）、`hdbcfg/mss_nvi_db.xml`（NV 目录）、`diag/*_msg_struct_def.txt`（结构定义）、`nv/nv_app_struct_def.txt`（NV 结构）。

> **8765 的 NV 目录不读 `mss_nvi_db.xml`**（2026-11-18 源码+实测）：它读两份宿主侧产物 `C:\fc_diag_client\data\nv_catalog.json`（项目录）与 `data\nv_structs.etypes`（结构体布局），由 `nv_db.py` 在启动时加载。
>
> **`/api/prim/reload` 只装 PrimDb，不碰 NV**；路由表里也没有 NV 目录/结构体的上传端点（只有 `nv/item|items|read|write|summary`）——NV 这部分**没有 HTTP 接口**，必须用服务目录里自带的工具与构建产物：
>
> ```bash
> # 1) 用固件 NV 配置重生目录快照（脚本支持传参，无需手工拷 json）
> python3 /mnt/c/fc_diag_client/make_nv_catalog.py \
>   <plc-sdk>/device/soc/vendor/DW31v100/config/nv_config/DW31/cfg/mcore_default.json
> # 2) 同步结构体布局（固件构建产物 database.etypes）
> cp <plc-sdk>/out/DW31v100/build/database.etypes /mnt/c/fc_diag_client/data/nv_structs.etypes
> # 3) 用接口重启服务（8766）——这一步才是 API
> curl -X POST http://127.0.0.1:8766/api/v1/services/diag/stop
> curl -X POST http://127.0.0.1:8766/api/v1/services/diag/start
> ```
>
> 判读：只做 1) 不做 2)，`nv-read` 能出 `item.name`/`structure` 但 `decoded.fields` 为空；只重启不同步，仍是旧的 96 项。
> 另注：`mss_nvi_db.xml` 里的 `ID` 是**十进制**（`ID="1108"` = `0x454`），用十六进制 grep 会误判"没生成"。

**日志通道（2026-11-18 实测定因，细节见 `hs-dw31-diag` → `references/logs.md` §8）**

- 日志三层：①设备 `0x5310` 模块上报开关（记录出不出串口）→ ②宿主 `mss_prim_db.xml`（msg_id 能否渲染文字）→ ③服务是否已加载该 XML（`prim/reload`）。
- app / mrs 层日志的 module = `TD_MOD_ID_APP_COMMON` = **812 = `0x32C`**，**默认关**；MAC/PHY 用 `0x200`，厂商工具每次连上都会开它 → 所以"只有网络层能打"。
- 开口令：`POST /api/send {"cmd_id":"0x5310","param_hex":"2c030001"}`（+ `2c030101` / 兜底 `ffff0001`）；**模块复位后必须重发**。
- `0x5517` 级别开关**不需要**：INFO 级实测可过。
- 升级脚本 `hs-dw31-upg/scripts/flash.py` 会在回连后**自动同步 prim XML**（优先 `/api/prim/upload`，回落 `/api/prim/reload`）。

## 3. 烧录门禁、状态机与模块状态

### 3.1 状态机

```
IDLE ──prepare──► PREPARED ──用户对话允许──► commit ──► FLASHING ──► DONE / FAILED / ABORTED
   ▲                  │                                     │
   └── TTL/取消 ──────┘                                     └── stop ──► ABORTED
```

- `prepare`：校验 magic / 镜像表 / 边界，算 `sha256`、大小，读当前 `0x3013` 版本与拓扑 MAC，生成 `approval_id`（TTL 120 s，一次性）。**绝不写 flash**。
- `commit`：校验 `human_confirmed === true`（字符串 "true" 不接受）、approval 未过期未使用、SHA256 与 prepare 一致**且文件未被改动**、无进行中任务、端口未让出、已登录。通过后起传输线程。
- 授权：`approved_by` 取 `web|mcp|cli|ai`；为 `mcp/cli/ai` 时 `user_approval` 必填（用户原话/摘要）。审计写 `flash.commit`。
- **授权方式**：用户在对话中明确说"允许 / 可以烧 / 直接升"即为授权，AI/CLI 直接提交；**不要求**用户去网页点按钮（网页按钮只是可选入口）。
- 永久禁止：`/api/upg/load`、`/api/upg/start`（绕过门禁）。

### 3.2 包路径白名单

服务端维护 `PKG_WHITELIST`（当前为 `C:\fc_diag_client` 与 `\\wsl.localhost\<distro>\home\<user>\gw\plc-project\out` 整棵 `out/`；以现场服务配置为准）。`prepare` 报 400「路径不在白名单」时：

1. 把包复制到服务可读的白名单目录（如 `C:\fc_diag_client\samples\`）再 prepare；或
2. 请服务维护者把工程 `out/` 根加进白名单。

不要靠改 Windows 绑定/端口转发绕。

### 3.3 `0x3415` 块头（12 B，必须完整）

```
u16 check_sum      = sum(本块数据字节) & 0xFFFF
u16 file_blk_size  = 本块真实数据长度（300；末块为余数）   ← 填 0 必失败
u32 upg_id         = zlib.crc32(整包)
u16 req_sn         = idx-1
u16 idx            = 1 起
u8  data[...]
```

- 成功块**没有逐块 ACK**（静默），进度只能看 `0x3410` 的 `last_blk_idx` / `rcv_file_size`。
- `file_blk_size` 填 0 → 首块即 `0x8000350D (UPG_FILE_CRC_INCORRECT)`、`upg_status=0xFF`、`rcv_file_size=0`。

### 3.4 `0x3410` 状态（60 B，`ext_upg_status_ind_s`）

param 必须 4 B `00000000`（空 param 模块不回复）。应答 60 B：

| 偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| 0 | u32 | `upg_id` | 文件 CRC32 |
| 4 | u32 | `blk_size` | 固定 300（**不是**进度） |
| 8 | u32 | `file_size` | 包总长（**不是**已收） |
| 12 | u32 | `num` | entry 数，CCO 自升级为 1 |
| 16 | u16 | `last_blk_idx` | 已接收块数（进度看这个） |
| 18 | u16 | `error_code` | 0 = 无错误 |
| 20 | u32 | `rcv_file_size` | 已收字节（进度依据） |
| 24 | u8 | `upg_status` | 0=OK，1=END(验证中)，8=UNKNOWN，0x10=STOPPING，0xF0=PROCESS，0xF1=TRANSMIT，0xFF=FAIL |
| 50 | u8[6] | `mac` | 模块 MAC |
| 56 | u32 | `upg_end_time` | 本轮耗时（秒） |

⚠ **按旧布局（`ext_upg_status_ind_entire`）解析会把偏移 20 的 `rcv_file_size` 低字节读成状态**（例如把 458000 的低字节 `0x10` 报成 `STOPPING`、把 458336 的低字节 `0x60` 报成未知值），形成"假绿/假红"。**包长一变低字节就变，所以它永远不能当状态**：状态只认偏移 24，进度只认偏移 16/20。一律按上表。

### 3.5 `0x3419` 复位与重连

- `0x3419 affirm {upg_id, reset_interval, option}` 后模块在 `reset_interval` 秒复位（默认 3 s，范围 0–3600）。
- 复位后原 COM 句柄"能写不能收"：服务发完立即 `close()`，等 `max(2, reset_interval+2)` 秒再 `open()` + SRP 重登；WSL 侧**不要自己开串口**。
- `0x3411 finish` 可能无应答（`finish_rc=null`），正常，不判失败；`0x3419` 的"应答"就是重启本身。
- 复位后 `GET /api/version` 是缓存，必须 close/reopen 后再读。

### 3.6 `GET /api/upg/progress` 关键字段

```
state, approval_id, package{sha256,size},
progress{sent,total,acks(固定0),percent,last_blk,status_polls},
module{upg_id,last_blk_idx,error_code,rcv_file_size,upg_status,upg_status_text,mac,upg_end_time,finish_rc,affirmed},
activation{confirmed,target_version,version_before,version_after,note},
reboot{reset_interval,reboot_at,source,reconnect_ok,reconnect_at,reconnect_error},
started_at,finished_at,error,version_after
```

- `progress.acks` 固定 0，**不要看**。
- `activation.confirmed` 仅在 `0x3013` 版本串包含目标 `SPCxxx` 且烧录前不存在时为 `true`；同版本重刷保持 `null`。

## 4. 成功判据（两层都过才算成功）

### 4.1 传输层（全中）

- `progress.sent == progress.total`（100%）；
- `module.rcv_file_size == 包字节数`；
- `module.upg_id == zlib.crc32(包)`；
- `module.error_code == 0`；
- `module.upg_status ∈ {0, 1}`（`0xFF` 或其他值判失败）。

### 4.2 激活层（拿到"新镜像在跑"的证据）

- **CCO/STA**：`0x3013` 版本串含目标 `SPCxxx`（烧录前不存在），且 `progress.reboot.reconnect_ok == true`；或 `activation.confirmed == true`。
- **ECU / 融合终端**：管理口 `link` 回 `0x81` 且型号串与本次构建一致，**旧镜像特征消失**；`0x3013` 取自 NV、不随编译变，不能单独当判据（用临时运行标记法，见 `upgrade.md` §8.4）。
- 复位证据三取一：`reconnect_ok == true`；close/reopen + 重登后版本/行为变化；`0x3013` 读取前后出现重启间隙。

**`state == "DONE"` 只代表传输与收尾命令已发出，不代表镜像已切换。** 缺 §4.2 的证据 = 失败。

### 4.3 失败兜底顺序

1. `upg_status=1(END)` 但 §4.2 不成立 → 判"传输成功、未激活"，转 1376.2 本地升级路径（`upgrade.md` §6.3）。
2. 1376.2 段 ACK 异常 → 先查单帧 512 B 上限与 `data_len`（`upgrade.md` §6.3.2），不要换包试。
3. **禁止**"手工写 NV `0xF05` + 重启"兜底（见 §5）。
4. 都失败 → BurnTool 整包救援（需停 8765 释放串口 + 断电/上电），并记录该变体 diag 路径不可用。

## 5. 禁止与边界

- 不做串口、不做协议解析、不做构建（构建在工程侧 `scripts/build.sh`）；WSL 侧不自己开串口。
- 不碰 `/api/upg/load`、`/api/upg/start`；不并发发设备命令。
- **不手工写 NV `0xF05`**（`ext_nv_ftm_startup_cfg`）当提交：flashboot 不认，load 地址猜错会把板子带进失联（两路串口全静默），只能 BurnTool 整包救援。`0xF05` 只允许 UPG 自己写。
- 不修改 Windows 服务绑定/端口转发、不塞环境变量让命令"看起来通过"。
- 不编造解码值：`decoded`/`decoded.fields` 缺失或 `note` 非空时如实说明。

## 6. 字段字典（只列技能会读的）

| 对象 | 字段 |
|---|---|
| state | `port,baud,logged_in,port_open,start_running,mode,module_ver,error,rx,tx,reconnect_count,last_reconnect,logfile` |
| frame | `id,ts,dir,type,secure,cmd_id,cmd_name,psize,size,param_hex,crc_ok,decrypted,decoded` |
| topo entry | `mac,tei,proxy_tei,level,ability,role,product,online,phase_text,spc_ver,sw_ver,b_ver,version_time` |
| nv item | `key_id,key_hex,name,module,structure,status,cco` |
| nv read | `nv_id,rc,rc_text,crc,crc_ok,data_hex,data_size,decoded` |
| nv write | `nv_id,rc,rc_text,data_size,verify.match,verify.data_hex` |

## 7. 实测基线（写入日期，供判读参考）

- 2026-11-12：CCO 458000 B / 1527 块 / 52–62 s；`0x3415` 全程无 ACK；MAC `00:C9:36:47:58:69`。
- 2026-11-13：`file_blk_size` 修好后 `0x3419` + close/reopen 可激活；SPC051 包 1531 块切换成功。
- 2026-11-16：ECU/融合终端变体走 diag 在线升级可切换（`0x3419` 后 3 s 重启）。
- 2026-11-17：融合终端只接受 `out/sg_fusion_cco/` 的在线包，烧 CCO 族包 → `0x8007(EXT_ERR_BAD_DATA)`；服务 0.3.1 提供 `prepare/commit/progress/stop/reboot`；`0x3410` 正确布局实测（458000 B、1527 块、`upg_status=0`）。
