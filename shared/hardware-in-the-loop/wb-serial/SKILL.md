---
name: wb-serial
description: 什么时候用我：要驱动工作台串口时——开/关 cco、sta 模块串口会话、发串口指令、增量读模块日志、做 module_log 实时观察取证、判读 CCO 日志、配置串口 Profile/端口映射、烧录时的串口侧配合，以及**任何开串口动作之前的 serial-bridge preflight**（烧录本身的判定归 `/root/.dsh/skills/wb-flash/SKILL.md`，不在本技能展开）。串口一律走 Python 串口桥（Windows COM ↔ TCP ↔ WSL PTY），需要工作台在线（默认 8790）。只解析/构帧/回验、手头只有报文不要串口的，用 /root/.dsh/skills/wb-appframe/SKILL.md；AI 任务门面与授权用 /root/.dsh/skills/ai-control-plane/SKILL.md。
argument-hint: "[任务，如 开cco串口发指令 / 盯cco日志直到出现XX / 串口桥验证]"
metadata:
  author: reasonix
  version: 1.0.0
  applies-to: 任意工作区（工作台默认 http://127.0.0.1:8790；<WORKBENCH_ROOT> 解析见 /root/.dsh/skills/wb-base/SKILL.md §1.1）
  source: 拆自 ai-control-plane（2026-10-28）
---

# 日志串口监听 / 模块串口会话（wb-serial）

**边界**：本技能只讲**在线驱动串口**这一段——串口桥 preflight、模块串口会话（ensure/stop/send）、日志增量读取、module_log 实时观察、CCO 日志判读、串口 Profile/端口映射。**烧录只讲串口侧配合**，成/败判定唯一 owner 是 `/root/.dsh/skills/wb-flash/SKILL.md`。归别的子技能的事：帧解析/构帧/回验、离线数据源直查 → `/root/.dsh/skills/wb-appframe/SKILL.md`；AI 任务门面 v2、授权签发、证据分级 → `/root/.dsh/skills/ai-control-plane/SKILL.md`（老门面，迁移期只读，勿改）。

## 1. 开串口前必做：serial-bridge status + verify（血泪教训，先做这一步）

**顺序不可颠倒、不可跳过**：工作台串口默认走纯 Python 桥（Windows `serial_bridge.py windows` ↔ TCP ↔ WSL `serial_bridge.py wsl`）。源文档的硬性要求是：**桥不通时不要继续 ensure / open / verify**——否则要么白开一次，要么把物理口占住，后面谁都用不了。

```bash
curl -s http://127.0.0.1:8790/api/serial-bridge/status | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8790/api/serial-bridge/verify \
  -H 'Content-Type: application/json' -d '{"ports":["<mapping_id>"],"open":true}' | python3 -m json.tool
```

- `GET /api/health` 先确认工作台在线，再 status、再 verify，**最后**才 `module-actions` / `module-sessions` / `simcon` / `simeter`。
- **默认只验目标口**（上例的 `ports:["<mapping_id>"]`）：不带 `ports` 的全量 verify 会把别的口的状态算进 `ok`，`{}` 一次就可能得到假的失败。
- **成功特征按口判定**：目标口 `workbench_ready=true` 且（`checks.open_ok=true` **或** `checks.in_use=true`）。`ok` 只是全局汇总，**别的口离线不阻塞本口**；**`ok=false` 只在目标口自身 `ports[].errors` 非空时才算阻塞**，此时按 errors 报层级。
- 口被已有会话占住时 `checks.open_ok=null` + `open_error="端口被工作台会话占用，跳过打开检查"` + `in_use=true`，`ok` 仍可能是 `true`；`in_use=true` 只说明该口**此刻无法自证可打开**，不是失败。
- verify 的 `open` 参数：`{"ports":["simcon"],"open":true}` 可只验指定口；`open=false` 跳过打开检查（`GET` / `POST` 同一响应形状，`POST` 才带 body；`status` 只读、不打开串口）。

> 来源：validation-20261028/F1（T1 实机：`factory` COM7 未接 → 全局 `ok=false`，`cco-main` 的 `workbench_ready=true`；`cco-main` 被占时 `open_ok=null`+`in_use=true`+`ok=true`）

### 1.1 为什么必须做（三层机制，不讲原理就会反复踩）

| 机制 | 事实 | 踩错的后果 |
| --- | --- | --- |
| **符号链接在哪** | 桥在 WSL 侧创建 PTY，并以**软链**暴露：`/run/hplc/serial/<mapping_id>`（如 `/run/hplc/serial/cco-main`）。`config/serial_ports.json` 的映射**必须指向该软链** | 映射没指向软链 → `工作台映射 ... 未指向桥接软链`，`workbench_ready=false` |
| **PTY 侧 parity 恒 N** | PTY **不接受 `PARENB`**，所以映射 `parity` **必须为 `N`**；真实 E 校验固定在 Windows 侧 `config/serial_bridge.json` | 写 `parity:"E"` → `checks.open_ok=false` + `Invalid argument`，verify 永远过不去 |
| **双通道** | `channel_ok` = WSL 桥在跑 + PTY 软链是字符设备 + Windows **数据**通道 + Windows **控制**通道（控制口 = `tcp_port+1000`，动态波特率靠它） | `control_connected=false` → 动态波特率不可用，应用改 baud 时 Windows 侧不跟随 |

### 1.2 判读字段

| 字段 | 含义 |
| --- | --- |
| `ok` | 本次查询范围内全部启用口 `channel_ok`（verify 时还要求 `workbench_ready`） |
| `summary` | `total` / `enabled` / `channel_ok` / `workbench_ready` 计数 |
| `ports[].channel_ok` | 桥进程 + PTY 软链 + 数据通道 + 控制通道四项齐 |
| `ports[].workbench_ready` | `channel_ok` 且 `serial_ports.json` 映射指向该软链、`parity=N` |
| `ports[].bridge.client_connected` | Windows 数据通道已连接 |
| `ports[].bridge.control_connected` | Windows 控制通道已连接（动态波特率依赖它） |
| `ports[].bridge.desired_baud` | WSL 应用当前要求的波特率（切换后 Windows 会跟随） |
| `ports[].mapping.baudrate` | `serial_ports.json` 映射的波特率；**verify 按它打开 PTY** |
| `ports[].checks.open_ok` | pyserial 能以 `parity=N` 打开；`false` 看 `open_error` |
| `ports[].checks.in_use` | 端口已被工作台会话占用时跳过打开检查 |
| `ports[].warnings` / `errors` | 可直接向用户/上层报告的具体原因 |

### 1.3 目标口 `errors` 的分层归因（照 errors 说，不要猜）

| errors 内容 | 处理 |
| --- | --- |
| `wsl_bridge 未运行` | 先起 WSL 桥：`python3 tools/serial_bridge/serial_bridge.py wsl start --config config/serial_bridge.json` |
| `Windows 侧数据/控制通道未连接` | Windows 桥没起，或 `windows.host` / 端口不一致 |
| `桥接软链不存在` | WSL 桥没起 / `link_dir` 不可写 |
| `工作台映射 ... 未指向桥接软链` / `parity 必须为 N` | 先改 `config/serial_ports.json`（改配置，不要绕过 verify） |
| `wsl_bridge.lock` 被占用 | 已有实例；`wsl status` 看 pid，必要时 `wsl stop` |

> 来源：references/serial-bridge.md:1-128、SKILL.md:48-66、api-contract.md:478-490

## 2. 会话生命周期：ensure / send / stop（幂等语义）

### 2.1 ensure（幂等：创建或复用并打开）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/ensure \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"module":"cco","mapping_id":"cco-main"}'
```

- **优先 `mapping_id`**（`cco-main` / `sta-main`）：波特率等参数按 `config/serial_ports.json` 映射自动走。**实际 COM 号随接线变化，别硬编码 COM 号**；也可直接传 `port`。
- 幂等语义：**已存在则复用，不存在则创建并打开**。返回 `session_id`（形如 `ms-xxxx`），`state=running` 表示串口已开。
- **会静默复用别人建的会话**：v2 `module-actions` 的 job 里 `result.owned=false` 就是"复用了前端/上一轮留下的会话"（实测复用了 2026-10-27 21:43 建的 `ms-e42e73a9a3c3`）。`owned=false` 时 **stop 前先确认该会话归属**，别把别人/前端正用的会话停掉。
- `409` = 串口被占用（前端或另一会话占着）→ 等释放或改口，**这是物理独占规则，不是 bug**；`503` = 串口不可用。

### 2.2 send（发送指令）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/<session_id>/send \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"text":"你的字符串","append_newline":true,"client_request_id":"<幂等ID>"}'
# 或十六进制：{"data_hex":"68 00 ..."}
```

- `200` + `state=succeeded` 即成功；`result.sent` 是字节数。
- 一律带 `client_request_id`（或用请求头 `Idempotency-Key`）：同 ID 重复提交复用原操作，内容不一致返回 409。

### 2.3 stop（停止，释放物理串口）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/<session_id>/stop \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"force": false}'
```

- `409` + `"会话仍有活动观察任务，不能停止"`：会话有活跃依赖（**如观察任务**）时普通 stop 拒绝。先查是哪个观察：`GET /api/ai/v1/operations?...`（要 token）或直读 `<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json` 里该会话的 op；能等就等它到终态，要撤就 `POST /api/ai/v1/operations/{id}/cancel`（`observation:create`），确认放弃才 `{"force":true}`。
- **stop 之后会话转 `idle`、不会消失**（`GET /api/module-serial/sessions` 仍看得到它）；释放判据是 verify 里该口 `in_use=false` + `open_ok=true`。
- **v2 等价门面**（免 token，`local_full`）：`POST /api/ai/v2/module-actions`，action=`ensure`/`send`/`stop` → `202` + job → `GET /api/ai/v2/jobs/{id}`。实测：v2 stop job 可能停在 `waiting/running`（已知不收敛点），**以物理串口是否释放为准**，不要为等 job 终态把口一直占着。

> 来源：references/module-serial.md:1-48、references/operation-guide.md:156-183
> 来源：validation-20261028/F7（T1 实测：`owned=false` 复用 `ms-e42e73a9a3c3`；plain stop 409 → force → 会话转 `idle`）

## 3. 日志增量读取

```bash
# 动态会话：日志（lines + last_seq）；after=-1 = 当前缓冲尾部（≤5000 行）
curl -s "http://127.0.0.1:8790/api/module-serial/sessions/<id>/logs?after=-1"
```

- 响应键：`lines` / **`last_seq`** / `channel` / `session_id`——游标字段名就是 `last_seq`，没有别的名字。
- **`after=-1` 不是增量**：实测直接返回整段环形缓冲（**5000 行**，`last_seq=597513`）；真正的增量是把上一轮的 `last_seq` 作为 `after` 传回（实测 43 行、`last_seq=597556`）。第一轮用 `after=-1` 拿尾部、之后一律回传游标，否则每轮白读 5000 行。
- 不要自己拼 `after=0` 之类未定义值。
- 旧单/双通道形态仍保留：`/logs?after&channel`（`channel` 区分 cco/sta）。
- 响应单次上限**可观测为 5000 行**；更早的历史不要假设能无限回捞：长会话或要全量历史时，读落盘的日志文件 `data/logs/模块/cco/*.log`（判读见 §5），或对原始日志重建索引（`POST /api/listener/logs/open`，见 `/root/.dsh/skills/wb-listener/SKILL.md`）。

> 来源：api-contract.md:158-182
> 来源：validation-20261028/F7（T1 实测：`after=-1`→5000 行/`last_seq=597513`；`after=597513`→43 行/`last_seq=597556`）

## 4. 实时观察任务（module_log）——取证靠它

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/observations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "source": "module_log",
    "target": {"session_id": "ms-xxxx"},
    "window": {"mode":"live", "start":"now", "timeout_seconds": 180},
    "match": {"kind":"literal", "value":"发送成功", "case_sensitive": false},
    "context": {"before": 20, "after": 30},
    "client_request_id": "obs-001"
  }'
```

- 观察 = 「盯住某个数据源，等一条符合条件的内容出现，然后取证」；`window.mode=live` + `start=now` **只盯创建之后的新日志**。
- **铁律：先建观察，再制造目标事件**——先建后造，否则目标日志早已流过，只能等到超时。
- `context.before/after` 是取证时向前/向后附带的行数（上例 20/30），别写太大把上下文塞爆。
- 幂等 ID 也可用请求头 `Idempotency-Key`，`client_request_id` 缺省时取它；同 ID 内容不一致返回 409。
- 观察任务会占用会话 → 这也是普通 `stop` 返回 409 的典型原因（见 §2.3）。
- 有观察在跑时**不要**并发 stop/send 抢同一会话；要收工先停观察或 `force:true` stop，并确认物理口已释放。

> 来源：references/operation-guide.md:197-217

## 5. CCO 日志判读要点（发送侧真相）

> CCO 固件运行日志 = 发送侧真相：判定「真没发」还是「发了没抓到」靠它。位置 `data/logs/模块/cco/*.log`（打包布局 `.build_plain/data/logs/模块/cco/*.log`）。

行格式：`[yyyyMMdd-HH:MM:SS:mmm] [RX] <帧hex>`。`[RX]` 是该行日志的**读取方向**（CCO 日志口回读固件输出），**不是帧方向**；帧 hex 在行尾，可整段 grep。

| 帧 | 识别正则（整行 grep，小写化） | 含义 / 方向 |
| --- | --- | --- |
| **06F230 采集上报** | `06201c01`（或 `683300c3`） | CCO → 集中器，**被侦听台 `minute_reports` 统计** |
| **11E4 主动上报** | `11e4` | 另一主动上报通道，每周期稳定，冻结 = 上报 − 2 分钟 |
| **11E3 补采指令** | `11e3`（须词边界锚定） | CCO 下发补采（弱信号节点靠它补报） |

```bash
grep -aiE "06201c01" data/logs/模块/cco/*.log   # 06F230
grep -ai  "11e4"     data/logs/模块/cco/*.log   # 11E4
grep -aiE "(^|[^0-9a-f])11e3" data/logs/模块/cco/*.log  # 11E3，锚定词边界
```

- **11e3 误报坑**：`11e3` 会作为子串出现在别的 hex 里（如 `b11e3472`）。用词边界锚定，或确认该行在 `[timestamp] [RX]` 后是独立帧（真实 11E3 整行以 `11e3` 开头）。
- **冻结字段**：11E4 帧内 `0102 00XX` 的 `00XX` = 冻结分钟（如 `01020020` → 冻结 20 分），冻结时刻 ≈ 上报时刻 − 2 分钟；06F230 的 `0200 44/46/48...` 每周期 +2 是**周期序号**，`120109261400` 是**恒定帧生成时间戳，别误当冻结时刻**。
- **双通道务必分开**：查「分钟采集缺报」只看 06F230 通道，**别拿 11E4 的稳定当 06F230 也不缺**（11E4 不走 `minute_reports`）。
- **链路在线判定**：先 `grep -aE "串口会话打开|串口会话关闭" data/logs/模块/cco/*.log`；时段内无任何帧且前后有「关闭/打开」→ 链路断线，不是漏。
- 交叉验证：CCO 有 06F230 → 发了，再查侦听台索引，无 = 接收侧丢帧；CCO 无 06F230 但有 11e3 → 弱信号靠补采（发送侧慢）；无帧且无补采、链路在线 → 发送侧未发出。

> 来源：references/cco-log.md:1-69

## 6. 串口 Profile 与端口映射

```bash
curl -s http://127.0.0.1:8790/api/serial-profile            # {profiles{四槽}, slots}
curl -s http://127.0.0.1:8790/api/serial-profile/status     # 四槽当前状态与占用只读快照
curl -s http://127.0.0.1:8790/api/serial-tags               # 角色↔COM 标签 + 在线端口 port_details
```

| 端点 | 关键语义 |
| --- | --- |
| `GET /api/serial-profile` | `{profiles{四槽}, slots}`；配置损坏返回 422 |
| `PUT /api/serial-profile` | `{profiles:{slot:{mapping_id, enabled, baudrate, parity, bytesize, stopbits}}}` → `{saved:true, profiles}`；**只保存不碰硬件**，未知映射/非法 422 |
| `POST /api/serial-profile/apply` | 应用已保存版本（module/listener/simcon 槽）；应用器未配置 503 |
| `GET /api/serial-profile/status` | 四槽只读快照（ADR-35），**不打开/关闭任何串口** |
| `GET/PUT /api/serial-tags` | 角色↔COM 标签映射；PUT 落 `data/runtime/serial_tags.json`，**只落盘不碰硬件** |

**唯一真相源是 `<WORKBENCH_ROOT>/config/serial_ports.json`**（运行时以 `/api/serial-bridge/status` 的 `ports[].mapping` 为准）：本篇**不复制映射表**，也**禁止在文档里再抄一份映射表**——旧表把 COM/baud 记错，已被实机推翻。实机对照（2026-10-28 盲测，只用于核对 status、不作判据）：`cco-main=COM8`、`sta-main=COM9`、`listener=COM11`、`simcon=COM4@115200`、`factory=COM7（未接，全局 `ok=false` 就是它拉下来的）`；WSL 侧一律 `/run/hplc/serial/<mapping_id>`。

- **认 `mapping_id`，不认 COM 号**：`cco-main` = CCO 日志口（实测日志含 `beacon send` / `onnet=` / `bpsCheck`）；`sta-main` = STA 日志口（某次 8 秒窗口无输出、`reboot` 无回显 → STA 可能未上电/静默，先验电源别先改配置）。
- **映射 baud 必须与业务/CCO 当前落点一致**：verify 按映射 baud 打开 PTY，supervisor 再经控制通道切 Windows 物理口；**不要用桥配置默认 115200 覆盖业务 baud**。`simcon` 口实测 **115200/E/8/1**（以 status 的 `mapping.baudrate` 为准）。
- CCO 口只在上电/复位后跑 bpsCheck，自适应序列 `bps:1`→9600E、`bps:3`→115200N、`bps:2`→115200E；`gSysPara.cac.local_rx_ok=1` 后不再重跑。复位用本地 1376.2 `01H-F1`（CCO 回 `00H-F1`，约 7 秒后重启），再用 14-F2 应答任务等待；**匹配 14-F2 时 `fn` 用十进制 `2`，不是 242**。
- 应用改 `ser.baudrate` 时 WSL supervisor 轮询 PTY termios 并经控制口通知 Windows 重开 COM，**切换瞬间有几十毫秒中断，协议侧要能重试**。

> 来源：api-contract.md:424-433、references/serial-bridge.md:53-95
> 来源：validation-20261028/F2（实机 `cco-main=COM8`/`sta-main=COM9`/`listener=COM11`/`simcon=115200`/`factory=COM7 未接`，与 `config/serial_ports.json` 一致）

## 7. 烧录：本技能只讲串口侧配合（判定不在这里）

> **owner 声明**：烧录的提交、`job_id`、幂等洞、`BURN SUCCESS` 判定、烧后回读横幅 —— 唯一 owner 是
> `/root/.dsh/skills/wb-flash/SKILL.md`。本节只留串口侧必须知道的四条，**不重复判据**。

1. **只认 `iap_*.bin`**：`flash_*.bin` 是生产整片镜像（~2MB），bootloader 路径不认，实测 ~24%（约 503KB）后模块停止 ACK 并中止；`upgrade_*.dat` 是另一条格式，与 XMODEM 无关。
2. **授权 `firmware_roots` 必须包含 `bin_path`**，否则 403「未配置允许烧录目录」（这是设计，不是缺陷）。
3. **桥无 DTR/RTS/流控**，XMODEM 动态波特率未在桥上完整验证 → 烧录仍建议单档；烧录期间不并发重试、不抢同一物理口。
4. 烧录前先按 §1 做 bridge `status`+`verify`；烧完 `stop` 会话释放串口。

> 来源：references/module-serial.md:49-68、references/serial-bridge.md:106

## 8. 红线（串口行为边界）

1. **同一时刻只有一个持有者**：同一物理串口同时只能一个会话持有（AI 与前端共享规则）；409/端口占用**不是故障**，等释放或改口，不硬抢。
2. **用完即关**：任务结束就 stop/close 释放；v2 stop 卡 `waiting` 时以**物理串口释放**为准，不要挂着不关。
3. **不找 `/dev/ttyACM*`、`/dev/ttyUSB*`**：一律走 serial-bridge 的软链 `/run/hplc/serial/<mapping_id>`，或按 `mapping_id` 由工作台解析；硬编码 COM 号/设备节点会在换线、换机后静默错口。
4. **开串口前必跑 status + verify**：**目标口** `workbench_ready=false` 不 ensure/open（别的口离线不算）。
5. **先建观察再制造事件**：module_log 只盯创建之后的新日志。
6. **不可取消的操作**（烧录/verify）耐心等终态，不并发重试。
7. **人机交接**：要让 Windows 用户用口，先 `wsl stop` 释放全部桥端口；不抢不藏。

> 来源：SKILL.md:232-248、references/serial-bridge.md:96-112

## 9. 已弃用做法（见到就换掉）

| 旧做法 | 状态 | 现在怎么做 |
| --- | --- | --- |
| **usbipd attach** 把 COM 映射进 WSL，再按 `/dev/ttyACM*` / `/dev/ttyUSB*` 找口 | **已弃用（2026-10-22 起）** | 走 Python 串口桥；`serial_ports.json` 的 `usb_busid` 已清空，映射改指 `/run/hplc/serial/*` |
| 用 `config/serial_ports.json.usbipd-backup-20261022.json` 恢复 usbipd 映射 | **不要单独做** | 要么保持 usbipd detached，要么恢复备份**并停 WSL 桥**，二者不能并存 |
| PTY 侧写 `parity:"E"`（把真实偶校验配在 WSL 侧） | **已弃用** | 映射 `parity` 恒 `N`，真实 E/O 在 Windows 侧 `config/serial_bridge.json` |
| 在会话里硬编码 COM 号（`"port":"COM9"`） | **已弃用** | 用 `mapping_id`（`cco-main`/`sta-main`/`simcon`/`listener`） |
| 用桥配置默认 115200 覆盖业务 baud | **禁止** | verify 按 `serial_ports.json` 映射 baud 打开；业务 baud 由 CCO 落点决定 |
| 旧版 `uart-map.ps1` / 卡在 Hyper-V 防火墙检查的脚本 | **已弃用** | 用新版 `uart-map.ps1 -Action bridge-toggle\|bridge-start\|bridge-stop\|bridge-status`；菜单 [6]/[7] 一键启停与查状态，[3] 的 usbipd 视图有 3 秒超时 |
| 从 WSL 的 UNC 当前目录 `cmd start` 起 Windows 桥 | **禁止** | 复制到 Windows 本地目录后用 `pythonw.exe` 常驻（会话级 `python.exe` 只适合调试） |

> 来源：references/serial-bridge.md:1-5、:64-67、:96-112、:115-122、references/module-serial.md:21-23

## 10. 交叉引用

- 帧解析 / 构帧 / 回验 / 离线数据源直查：`/root/.dsh/skills/wb-appframe/SKILL.md`
- 烧录提交后的成/败判定与回读核对：`/root/.dsh/skills/wb-flash/SKILL.md`
- 已解析帧查询、通信流三段证据链、组网/入网诊断：`/root/.dsh/skills/wb-listener/SKILL.md`
- 路径根解析、AI 任务门面 v2（`investigations`/`module-actions`/`flash-jobs`/`evidence`）、授权、证据分级：`/root/.dsh/skills/wb-base/SKILL.md`
- 模拟集中器 simcon（verify / step / recv_only / frames / store）：`/root/.dsh/skills/wb-simcon/SKILL.md`
- 契约口径（endpoint / 前缀 / 红线的原始事实来源）：`/root/.dsh/skills/ai-control-plane/SKILL.md`（老门面，迁移期只读，**勿改**）
- 串口桥部署/常驻/故障全量：项目技能 `skills/share/serial-bridge/SKILL.md`（相对 `<WORKBENCH_ROOT>`）；配置 `config/serial_bridge.json`、`config/serial_ports.json`；实机证据 `data/logs/serial_bridge_evidence_20261022/`


---

## 附录 · 深水事实库（事实来源，按节读，不复制）

本技能只讲**怎么做**。精确字段、全部端点、全流程手册在入口技能的事实库里，**只有本文答不清或要核对字段时才翻对应小节**，不要整份读：

| 文件 | 该读哪一节 | 行数 |
|---|---|---|
| /root/.dsh/skills/ai-control-plane/references/serial-bridge.md | 串口桥全部端点与 preflight 口径 | 129 |
| /root/.dsh/skills/ai-control-plane/references/module-serial.md | 模块日志会话全端点 | 69 |
| /root/.dsh/skills/ai-control-plane/references/cco-log.md | CCO 日志判读要点 | 70 |
| /root/.dsh/skills/ai-control-plane/references/api-contract.md | §4 模块日志 / §9 串口 Profile / §13 串口桥契约 | 491 |

- 旧门面归档（v2.9 路由表、实测校准段、REQS 编号索引）：/root/.dsh/skills/ai-control-plane/references/_归档-门面v2.9.md（257 行，**仅当新文档查不到时**参考）

> 铁律：事实库里改动只改一处；子技能里**不复制**事实库内容，避免两份说法打架。
