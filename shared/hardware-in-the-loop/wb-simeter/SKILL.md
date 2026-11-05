---
name: wb-simeter
description: 什么时候用我：要调模拟电表（sim_meter，645/698 双协议从站）——查电表脑/串口/会话状态、开表口、喂一帧 645 请求看应答帧、配 698 采集 OAD 数据集、改档案地址做对档联调、改表内数据或时钟、配重庆即装即采、查会话帧日志。只讲模拟电表这一个服务：模拟集中器本体去 wb-simcon，串口会话与桥 preflight 去 wb-serial，烧录去 wb-flash，离线帧解析去 wb-appframe。
argument-hint: "[任务，如 开表口 / 喂一帧645读电能 / 对档联调改地址 / 查电表帧日志]"
metadata:
  author: reasonix
  version: 1.2.0
  applies-to: 本机工作台 8790（`/api/simeter/*`，三形态同路径）；独立版端口见部署表
  source: 拆自 ai-control-plane（2026-10-28）
---

> v1.1.0（2026-11-03）：REQS-0037 — 新增 698 采集 OAD 数据集（`GET/POST /oad`，file/runtime/effective 三层视图，API>文件，缺项 missing 不应答）；定位补 698（645/698 双协议从站）。

# 模拟电表子技能（wb-simeter）

**本技能只讲模拟电表 `sim_meter`（645/698 双协议从站）的 HTTP 面：观察、开口、喂帧、改表态、对档联调。**
别的事不归我：模拟集中器（simcon）验证/单步/档案 → `wb-simcon`；串口会话、串口桥 preflight 细节、CCO 日志 → `wb-serial`；烧录固件 → `wb-flash`；纯离线帧解析/构帧 → `wb-appframe`；授权与 v2 总门面 → `ai-control-plane`（只读总入口）。
本技能的端点全集与错误语义**以自描述小抄 `GET /api/simeter/_meta` 为准**——响应内即契约，省 token 防迷路。

## 1. 定位（先弄清谁免 token、谁能写）

| 面 | 能力 | 鉴权 | 能做什么 |
| --- | --- | --- | --- |
| AI 平面（v2） | `simeter_frames.read`，scope `simeter:read` | 本机 loopback + `WORKBENCH_LOCAL_FULL_ACCESS=1` 免 token | **只读**：状态、帧日志、investigations 观察 |
| 直连服务面 | `/api/simeter/*` 全量端点 | **免 token** | 写操作（open/close/config/data/clock/handle_hex…）只走这里 |

- 写操作**不经 `/api/ai/v1`、不需要 Bearer**；但"免 token"只表示鉴权方式不同，不代表可以乱改表态（见 §6）。
- service 名固定 `simeter`（v2 investigations 的 `source` 就是它）。

> 来源：ai-control-plane/references/simeter.md；ai-control-plane/references/api-contract.md

## 2. 端点总表（14 个路径 + 自描述入口）

| 端点 | 作用 | 典型调用 / 关键返回 |
| --- | --- | --- |
| `GET /_meta` | 自描述小抄：`{service, endpoints{}, open_sequence[], errors{}, notes[]}` | `curl http://127.0.0.1:8790/api/simeter/_meta` |
| `GET /status` | 电表脑 + 串口 + 会话状态 | `{brain{addr,version,baudrate,…,rx_count,tx_count}, serial, session}` |
| `GET /ports` | 本机串口枚举 | `{ports, port_details}` |
| `POST /open` | 开串口并注册资源（注册表防双开） | `{"mapping_id":"listener"}` 或 `{"port":"/dev/pts/N","baudrate":2400,"parity":"E"}`；409 已打开/被占用 |
| `POST /close` | 释放串口并解除资源注册 | 空体；200 |
| `POST /baud` | 17H 波特率热切换 | `{"baudrate":9600}`；200 / 422 |
| `GET/POST /config` | 读 / 改 `{addr, version(07\|97), baudrate, parity, …}` | `{"addr":"999999999999"}`；200 / 400 |
| `GET/POST /data` | 读 / 设数据标识项 `{di（显示序 00010000）, value, scale（小数位）}` | 200 / 400 |
| `POST /clock` | 设置表内时钟 | `{"time":"YYYY-MM-DD HH:MM:SS"}`；200 / 400 |
| `GET/POST /jzjc`；`POST /jzjc/report` | 重庆即装即采配置；生成上送报文 | `{"style":"sta"\|"afn06f7"}` → 报文 hex；200 / 400 |
| `GET /oad` | 698 采集 OAD 数据集三层视图 | `file`/`runtime`/`effective`：file=文件载体（`data/oad_dataset.json`）、runtime=API 运行时集、effective=生效视图（**API 优先于文件**） |
| `POST /oad` | 设运行时 OAD 集（698 脑按数据集匹配 OAD 构应答） | `{"entries":[{"oad":"20000201","data_hex":"…","length":2}]}`；`missing:true` 缺项不应答 |
| `POST /handle_hex` | **无串口调测**：喂 645 请求帧 → 应答帧 | `{reply_hex, reply_wire_hex, note{…}}`；地址不符 `reply_hex:null` + `note.mine=false` |
| `POST /send_hex` | 串口已打开时注入原始帧 | `{"hex":"…"}`；200 / 409 |
| `GET /frames` | 会话帧日志 | `?dir=rx\|tx\|event&after_seq&limit` → `{session, entries[]}` |

- 环境注记：WSL pts 不接受 PARENB，经虚拟串口/桥接开口一律 `parity="N"`（线参由对端决定）。

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/simeter.md

## 3. 最小调用链（只读观察，先跑这四步）

```bash
# 1) 自描述小抄：端点清单 + open_sequence + 错误码语义
curl http://127.0.0.1:8790/api/simeter/_meta
# 2) 电表脑 + 串口 + 会话状态
curl http://127.0.0.1:8790/api/simeter/status
# 3) 会话帧日志（dir=rx|tx|event, after_seq, limit）
curl "http://127.0.0.1:8790/api/simeter/frames?limit=50"
# 4) v2 门面观察（随 capabilities 的 simeter_frames.read 一起用）
curl -X POST http://127.0.0.1:8790/api/ai/v2/investigations \
  -H "Content-Type: application/json" \
  -d '{"observations":[{"source":"simeter"}],"client_request_id":"<id>"}'
```

> 来源：ai-control-plane/references/simeter.md；ai-control-plane/references/operation-guide.md

## 4. 调测典型序列（`_meta.open_sequence`）

```bash
# 开表口：工作台模式优先 mapping_id（不要硬编码 COM 号）
curl -X POST http://127.0.0.1:8790/api/simeter/open \
  -H "Content-Type: application/json" -d '{"mapping_id":"listener"}'
# 或显式端口：{"port":"/dev/pts/N","baudrate":2400,"parity":"E"}

# 无串口调测：直接喂 645 请求帧 hex，返回应答帧 hex（不开串口也能验证表逻辑）
curl -X POST http://127.0.0.1:8790/api/simeter/handle_hex \
  -H "Content-Type: application/json" \
  -d '{"hex":"68999999999999681104333334334816"}'
```

- 判读：`reply_hex` 为 `null` 且 `note.mine=false` = 请求里的表地址不是本表当前地址（先 §5 改 `addr`），不是服务坏了。
- 调完 `POST /close` 释放；`409` = 口已被工作台其它会话占着（物理独占，不是 bug）。

> 来源：ai-control-plane/references/simeter.md；ai-control-plane/references/api-contract.md

## 4.1 698 采集 OAD 数据集（REQS-0037）

- **schema**：`entries:[{"oad":"20000201","data_hex":"…","length":2,"note":"…"}]`；缺项写 `{"oad":"20000200","missing":true,"length":2}`。
- **示例**：`curl -X POST http://127.0.0.1:8790/api/simeter/oad -H "Content-Type: application/json" -d '{"entries":[{"oad":"20000201","data_hex":"1101"},{"oad":"20000200","missing":true,"length":2}]}'`
- **缺项口径**：`missing:true` 的 OAD **不应答**；STA 读层按任务配置长度补 `FF`（实测 2026-11-03：20000201→1101、20010201→1102、20000200 缺项 length 2）。
- **三层优先级**：API 运行时集 > 文件载体 `data/oad_dataset.json`（示例 `libs/sim_meter/data/oad_dataset.example.json`；环境变量 `SIMETER_OAD_DATASET` 可指向自定义文件）。
- **与 `/handle_hex` 的关系**：handle_hex 喂 698 请求帧时也**按数据集应答**——缺项 OAD 同样不应答，未配置 OAD 行为与旧版一致。

> 来源：REQS-0037（2026-11-03 台架实测）

### 4.1.1 85 05 分块/分帧应答验证（req006 沉淀）

> **85 05 分块/分帧应答的验证走 `tools/scripts/minute_collect/` 下的构造器
> + send_hex 注入流程，不要重新造脚本。** 索引见其 README.md。

- `build_8505_block.py`（离线构 85 05 读块应答帧）、`build_link_frames.py`
  （APDU 超长时分帧 00/11/01）、`inject_8505_blocks.py`（**等 /frames 出现
  85 05 GET 请求 → 构帧 → `POST /send_hex` 按块注入 → 核对 tx 落帧**，需本服务
  串口已 open）。
- 口径：85 05 APDU = PIID-ACD→lastblock→block→CHOICE→data + 9B 尾（DL/T 698.45
  表 76）；链路层 SA=0x05+6B、C=0xC3，复用 `libs/parser_lib/.../build_frame`。
- 注意：simeter 本体**没有分块配置模式**，分块应答一律走 send_hex 注入；
  本服务 OAD 数据集（上节）只覆盖 85 02 一次性应答。

## 4.2 会话生命周期（2026-11-04 实测）

- **工作台重启会带走 simeter 串口会话**（旧 session 消失、/frames 归零）：重启后必须 `POST /api/simeter/open {"mapping_id":"simeter"}` 重开，否则 STA 的 698 WithList 全部无应答、冻结数据全缺。
- OAD 运行时层（effective）优先于文件层；`missing:true` 的 OAD 静默不应答；实验后务必 finally 恢复，否则后续冻结持续缺数。
- 判断"链路是否在动"先看 `/frames` 增量（跨会话归零重计），别看 brain 的 rx/tx 累计计数器。

## 5. 与模拟集中器对档联调（易踩点，逐条踩过）

| # | 口径 | 说明 |
| --- | --- | --- |
| 1 | **出厂地址 `000000000001`** | 与 simcon 档案地址不一致时，读数据得到「非本表地址，不响应」——**静默无应答**，最容易被误诊为链路故障 |
| 2 | **对档前先设地址** | `POST /config {"addr":"999999999999"}` 设成 simcon 档案地址，再跑抄表/对档 |
| 3 | **645 记法** | 地址 12 位 BCD；DI 用显示序（`00010000` = 正向有功总电能）；协议版本 07/97 可切 |
| 4 | **波特率** | 17H 特征字单字节 + `33H` 传输；热切换 `POST /baud {"baudrate":9600}` |
| 5 | **13H 读地址三种广播** | 支持 `FE×6` / `99×6` / `AA×6`（对齐 STA 绑表扫掠节奏） |
| 6 | **WSL pts 不吃 PARENB** | 经虚拟串口/桥接开口一律 `parity="N"`；pts 是透明管道，线参由 Windows 侧对端决定 |

> 来源：ai-control-plane/references/simeter.md；ai-control-plane/references/api-contract.md

## 6. 红线（改表态前必须遵守）

1. **改之前先备份**：`GET /config`、`GET /data` 把原 `addr / version / baudrate / parity`、目标 DI 的 `value/scale` 存下来，再 `POST`；改完回读核对，联调结束按备份还原。
2. **只改本次用例要改的项**：`/config`、`/data`、`/clock` 动的是表内真实状态，会污染后续用例与别人的对档。
3. **串口独占、用完即关**：同一物理串口同一时刻一个持有者；调完 `POST /close` 立即释放；`409` 等待或换口，不硬抢（与总技能「串口独占」同一条规则）。
4. **观察先建后造**：先开 `frames`/investigations 观察，再制造目标帧，否则事件已过去。
5. **别走 v2 改表**：v2 侧只有 `simeter_frames.read`（只读）；也别绕过工作台直连物理 COM。

> 来源：ai-control-plane/references/simeter.md；ai-control-plane/references/api-contract.md

## 附录 · 深水事实库（答不清时才翻，别整份读）

| 文件 | 该读哪一节 | 行数 |
| --- | --- | --- |
| `ai-control-plane/references/simeter.md` | 模拟电表端点全集与自描述 | 43 |
| `ai-control-plane/references/api-contract.md` | §5.1 simeter 契约 | 490 |

- 旧门面归档 `ai-control-plane/references/_归档-门面v2.9.md`（257 行：v2.9 路由表、实测校准段、REQS 索引）**仅当新文档查不到时**参考。
- 铁律：事实库改动只改一处；子技能**不复制**事实库内容，避免两份说法打架。
