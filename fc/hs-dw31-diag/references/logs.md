# 查看日志（logs）

适用：查模块状态、版本、原始帧、日志类帧、prim 解析行、prim 结构树、拓扑。

## 1. 状态与版本

```bash
CTL="python3 $BASE/scripts/fcctl.py"   # $BASE = hs-dw31-base 技能目录（先读 hs-dw31-base 拿到）
$CTL doctor
$CTL status
$CTL version
```

`status` 重点字段：`logged_in`、`port_open`、`start_running`、`mode`、`module_ver`、`error`、`rx`、`tx`。
`start_running=true` = Start.exe/MaintenanceKits 占用，端口已让出，停止设备命令。

## 2. 原始帧

```bash
$CTL frames --since 0 --limit 50
```

- `since` 用上一批 `last_id`；`limit` 上限 2000；
- 返回最新 `limit` 条；
- 字段：`id/ts/dir/type/secure/cmd_id/cmd_name/psize/size/param_hex/crc_ok/decrypted/decoded`。

## 3. 日志类帧

```bash
$CTL logs --since 0 --limit 100
```

只保留 `0x5304/0x5314/0x5315/0x5316`。

## 4. prim 解析行与结构树

```bash
$CTL prim --since 0 --limit 100
$CTL prim-frame --id <frame_id>
```

prim 行字段：`id/ts/category/no/tick/prim_id/prim_hex/prim_name/structure/source_hex/dest_hex/data_len/has_struct`。
`has_struct=false` 或 `note` 非空时不要硬解。

## 5. 事件

```bash
$CTL events --seconds 10
```

- 8765 无 SSE，CLI 轮询 `/api/logs`；
- 只报启动后的**新**事件；历史用 `logs --since`。

## 6. 证据口径

- 结论带帧 `id` + `ts`；
- 引用 `param_hex` 或 `decoded` 时原样引用，不二次编造；
- 统计类结论说明 `since`/`limit` 时间窗。

## 7. 导出与落盘（唯一约定）

- 目录优先级：`REQ_DIR/logs/` → `PROJECT/logs/` → 会话工作区 `logs/`（见 `SKILL.md` §5）。
- 取样并落盘：

```bash
LOG_DIR="${REQ_DIR:-$PROJECT}/logs"; mkdir -p "$LOG_DIR"   # 两个变量按 SKILL.md §1 解析
STAMP=$(date +%Y%m%d-%H%M)
$CTL frames --since 0 --limit 2000 > "$LOG_DIR/$STAMP-frames.json"
$CTL logs   --since 0 --limit 1000 > "$LOG_DIR/$STAMP-logs.json"
$CTL prim   --since 0 --limit 1000 > "$LOG_DIR/$STAMP-prim.json"
```

- 服务自有的 `service_frames.jsonl`、`audit.jsonl` 是**只读源**（实际路径看 `status.logfile`）；
  要长期留存就导出到 `REQ_DIR/logs/`，不要把它们当工作区。
- 结论写成一份 `REQ_DIR/logs/<STAMP>-report.md`（或追加到 `REQ_DIR/DONE.md`），引用帧 `id`/`ts` 与导出文件名；不要在多处留半份结论。

## 8 日志打不出来：5 分钟定因（2026-11-18 实测结论，别再重查）

**先记住结论：设备侧按 `module_id` 过滤，`0x5310` 没开该模块 = 记录根本不上线。**

### 8.1 三层模型（缺一层就是"看不见"）

| 层 | 决定什么 | 缺了的表现 |
|---|---|---|
| ① 设备上报开关 `0x5310` | 该 module_id 的 SYS 日志**出不出串口** | `0x5314` 帧里**完全没有**这个 msg_id（连 `(未知 msg_id)` 都没有） |
| ② 宿主 prim DB（`mss_prim_db.xml`） | 能不能把 msg_id 渲染成**文字** | 帧有，显示 `[0x…] (未知 msg_id) module=.. no=.. data=<hex>` |
| ③ 宿主已加载该 XML | ② 是否生效 | `status.prim.count` 不对；发过 `POST /api/prim/reload` 并核对 count |

### 8.2 关键事实（别再猜）

- app / mrs 层日志的 module 号 = `TD_MOD_ID_APP_COMMON` = **812 = `0x32C`**（`mrs_srv_cco.c:80`、`soc_config.h:77`），**默认是关的**。
- MAC / PHY（"网络层"）日志用 `module = 0x200`，厂商工具每次连上都发 `0x5310 00020001` + `00020101` 打开它 → **只有网络层看得见**，不是网络层特殊。
- module `0`（`soc_diag_util.h` 默认 `THIS_MOD_ID`）**默认就能过**，可作为对照探针。
- **不需要** `0x5517`（级别开关）：实测 INFO 级照样出来。
- 日志帧 `0x5314` 布局：`module(4) dest(4) no(4) msg_id(4) time(4)` + 参数，小端。
- **开关是 RAM 态，模块复位/升级后必须重发**。
- 文本不进镜像：`strings xxx.bin | grep <提示语>` = 0 处是**正常的**，fmt 被宏丢弃，文字只在 XML 里。

### 8.3 开口令（照抄）

```bash
CTL="python3 $BASE/scripts/fcctl.py"
$CTL send --cmd 0x5310 --param-hex 2c030001   # 开 module 0x032C（app/mrs 层），rc=0 即生效
$CTL send --cmd 0x5310 --param-hex 2c030101   # 同模块 is_dest=1（厂商对 0x200 就是成对发的）
$CTL send --cmd 0x5310 --param-hex ffff0001   # 兜底：全模块
```

判据：发完 **5 秒内** `$CTL frames` 应出现目标 msg_id（实测 15:29:26 首次出现，之前 70 s 零条）。

### 8.4 新写日志时只有三条要守

1. **id 用稳定常量**：工程惯例 `MRS_FILE_LOG_FLAG_xxx`（0x1–0x89，见 `soc_msg_log.h`）。
   **不要用 `__LINE__`**——插一行 id 就漂，固件与 XML 失配 → `(未知 msg_id)`。
2. **文件要有 `DIAG_FILE_ID_*` 映射**：在文件头 `#undef THIS_FILE_ID` / `#define THIS_FILE_ID DIAG_FILE_ID_<你的文件>`，
   并把 module 设成业务模块（`#define THIS_MOD_ID TD_MOD_ID_APP_COMMON`）。
   写在 `Application/` 等 prim 生成器扫不到的地方 → **XML 不会自动出条目，必须手补，见 §8.4.1**。
3. **text 只写提示语，参数另给**：`ext_diag_info_log2(FLAG, "AFE restored", target)`；
   `fmt` 不会上板，仅用于生成 XML 的 name。
4. **id 粒度按"一条消息"算，不按"一个打点"算**：同一句话的不同触发点共用一个 id，
   用参数区分阶段（例：`ECU_LOG_ID_INIT_FAIL = 0x101` + `stage` 1=队列/2=任务/3=管理通道/4=UART3）——
   这样 XML 只一行、不用维护 id 表；只有**文本语义不同**的消息才另配 id。
   共用一个 id 时把打点收进一个小函数（唯一调用点），XML 里就只生成一行。
   id 与 stage 常量**集中登记在工程头文件**（如 `Application/ecu_common/include/ecu_log_id.h`），
   不要散在各 .c 里；SDK 侧同款参照 `soc_msg_log.h` 的 `MRS_FILE_LOG_FLAG_xxx`。

#### 8.4.1 `Application/` 层日志：让组件参与 DB 生成（GW 工程已接通，2026-11-18 实测）

为什么需要这一步：日志宏只上报 `(module_id, msg_id, 级别, 参数)`，**中文文本不进镜像**，
由宿主 `mss_prim_db.xml` 按 msg_id 查表还原；而 XML 的日志条目由构建期 `create_db()` 扫组件源码生成，
SDK 只对自己的组件（`utils/net/plc/app/mrs`）调了它。`Application/` 下的工程组件是
`vendor_bridge.cmake.in` 用 `register_component` 注册的、没有 `create_db()` → 能编能报，但 XML 缺条目 →
台面只显示 `[0x…] (未知 msg_id)`。

**首选做法：在 bridge 里给组件接上 `create_db()`（已落地，一次配置，之后写日志不用碰 XML）**

```cmake
# Config/dw31_sg/vendor_bridge.cmake.in，register_component(...) 之后
set(COMPONENT_NAME dw31_sg_ecu_uart)
set(COMPONENT_SRC   <该组件的全部 .c，与 register_component 的 SOURCES 一致>)
set(COMPONENT_INCLUDE ${DW31_SG_ECU_INCLUDE})
set(COMPONENT_DEFINES ${TARGET_DEFINES} ${DW31_SG_PROFILE_DEFINE})
set(COMPONENT_FLAGS   ${TARGET_FLAGS})
create_db()
```

效果：构建期自动生成 `<MSG NAME="<fmt 原文> @文件(行),级别" ID="0x...." />`，`NAME` 直接取自
日志宏里的中文 `fmt`，无需手工维护 id 表。

**血泪约束（一定要守）：id 的十六进制写法只能含数字 0–9，不能出现 A–F。**
`mk_prim_xml_step2.py` 解析 id 时只截取末尾的**十进制数字串**再按十六进制解释：

| 源码里的 id | 生成器解析成 | 结果 |
|---|---|---|
| `0x0B3` | `0x3` | ✗ 与固件 msg_id 不符 → 台面"未知消息" |
| `0x101` | `0x101` | ✓ 正确 |

这也是 SDK 的 `MRS_FILE_LOG_FLAG_xxx` 只用到 `0x1–0x89`（跳过 A–F）的真实原因。
选 id 时用 `0x100`、`0x101`… 这类"全数字"值（14 bit 内，本文件唯一即可）。

**判据（两步都要验）**：

```bash
# ① XML 条目存在且 id 与固件常量一致
grep "ecu_port.c" Platform/plc-sdk/out/DW31v100/database_sg/cco/system/hdbcfg/mss_prim_db.xml
python3 -c "import struct,sys;d=open('<ecu_port.c.o>','rb').read();print(d.find(struct.pack('<I',0xabe01012))>=0)"
# ② flash.py 的 prim.count 覆盖它，台面显示中文
```

msg_id 公式（`mk_hdb_sg_xml.json`：file 14b / line 14b / level 4b）：

```
msg_id = (file_id << 18) | ((id << 4) & 0x3FFF0) | level      # level: ERROR=2 WARN=3 INFO=5
```

样例（ECU 端口，`file_id = DIAG_FILE_ID_FOR_USER0_MIN = 11000`）：

| id 常量 | id | msg_id | XML `STRUCTURE` |
|---|---|---|---|
| `ECU_LOG_ID_PORT_INIT_FAIL` | 0x101 | `0xABE01012` | `diag_log_msg1` |
| `ECU_LOG_ID_MGMT_INIT_FAIL` | 0x103 | `0xABE01032` | `diag_log_msg1` |

**兜底做法（不能改构建时）**：手工往
`Platform/plc-sdk/device/soc/vendor/DW31v100/config/database/<core>/system/hdbcfg/mss_prim_db.xml`
的 `<MSG_LOG>` 里加一行（step2 以它为 base 重新生成，`flash.py` 再整体上传）。
手补时 id 按上面公式算，不受 A–F 限制，但**每加一条日志都要同步维护**，容易失配——优先用上面的自动方案。

注意：**开机那一刻打的日志天生看不到**——module 812 开关是 RAM 态、开机默认关，
`0x5310` 之后才上报。要留开机记录，得让服务在连上后补发口令（0008 §5），或对该条改用 module 0。

### 8.5 自己的模块看不到时，先这样自证（A/B 探针）

同一个任务里打两组，**唯一变量是 module 号**：一组 `THIS_MOD_ID 0`、一组 `TD_MOD_ID_APP_COMMON`。
- 两组都有 → 开关是开的，问题在别处；
- 只有 mod0 有 → 就是 module 开关没开，发 §8.3 的口令；
- 发完口令 mod812 立刻出现 → 定因完成，不用再改固件。
