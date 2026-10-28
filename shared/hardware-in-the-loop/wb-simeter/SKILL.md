---
name: wb-simeter
description: 什么时候用我：要调模拟电表（sim_meter，645 从站）——查电表脑/串口/会话状态、开表口、喂一帧 645 请求看应答帧、改档案地址做对档联调、改表内数据或时钟、配重庆即装即采、查会话帧日志。只讲模拟电表这一个服务：模拟集中器本体去 wb-simcon，串口会话与桥 preflight 去 wb-serial，烧录去 wb-flash，离线帧解析去 wb-appframe。
argument-hint: "[任务，如 开表口 / 喂一帧645读电能 / 对档联调改地址 / 查电表帧日志]"
metadata:
  author: reasonix
  version: 1.0.0
  applies-to: 本机工作台 8790（`/api/simeter/*`，三形态同路径）；独立版端口见部署表
  source: 拆自 ai-control-plane（2026-10-28）
---

# 模拟电表子技能（wb-simeter）

**本技能只讲模拟电表 `sim_meter`（645 从站）的 HTTP 面：观察、开口、喂帧、改表态、对档联调。**
别的事不归我：模拟集中器（simcon）验证/单步/档案 → `wb-simcon`；串口会话、串口桥 preflight 细节、CCO 日志 → `wb-serial`；烧录固件 → `wb-flash`；纯离线帧解析/构帧 → `wb-appframe`；授权与 v2 总门面 → `ai-control-plane`（只读总入口）。
本技能的端点全集与错误语义**以自描述小抄 `GET /api/simeter/_meta` 为准**——响应内即契约，省 token 防迷路。

## 1. 定位（先弄清谁免 token、谁能写）

| 面 | 能力 | 鉴权 | 能做什么 |
| --- | --- | --- | --- |
| AI 平面（v2） | `simeter_frames.read`，scope `simeter:read` | 本机 loopback + `WORKBENCH_LOCAL_FULL_ACCESS=1` 免 token | **只读**：状态、帧日志、investigations 观察 |
| 直连服务面 | `/api/simeter/*` 全量端点 | **免 token** | 写操作（open/close/config/data/clock/handle_hex…）只走这里 |

- 写操作**不经 `/api/ai/v1`、不需要 Bearer**；但"免 token"只表示鉴权方式不同，不代表可以乱改表态（见 §6）。
- service 名固定 `simeter`（v2 investigations 的 `source` 就是它）。

> 来源：references/simeter.md:1-5；references/api-contract.md:223-227,236

## 2. 端点总表（13 个路径 + 自描述入口）

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
| `POST /handle_hex` | **无串口调测**：喂 645 请求帧 → 应答帧 | `{reply_hex, reply_wire_hex, note{…}}`；地址不符 `reply_hex:null` + `note.mine=false` |
| `POST /send_hex` | 串口已打开时注入原始帧 | `{"hex":"…"}`；200 / 409 |
| `GET /frames` | 会话帧日志 | `?dir=rx\|tx\|event&after_seq&limit` → `{session, entries[]}` |

- 环境注记：WSL pts 不接受 PARENB，经虚拟串口/桥接开口一律 `parity="N"`（线参由对端决定）。

> 来源：references/api-contract.md:223-245；references/simeter.md:1-5

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

> 来源：references/simeter.md:7-21；references/operation-guide.md:436-448

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

> 来源：references/simeter.md:22-33；references/api-contract.md:230,243

## 5. 与模拟集中器对档联调（易踩点，逐条踩过）

| # | 口径 | 说明 |
| --- | --- | --- |
| 1 | **出厂地址 `000000000001`** | 与 simcon 档案地址不一致时，读数据得到「非本表地址，不响应」——**静默无应答**，最容易被误诊为链路故障 |
| 2 | **对档前先设地址** | `POST /config {"addr":"999999999999"}` 设成 simcon 档案地址，再跑抄表/对档 |
| 3 | **645 记法** | 地址 12 位 BCD；DI 用显示序（`00010000` = 正向有功总电能）；协议版本 07/97 可切 |
| 4 | **波特率** | 17H 特征字单字节 + `33H` 传输；热切换 `POST /baud {"baudrate":9600}` |
| 5 | **13H 读地址三种广播** | 支持 `FE×6` / `99×6` / `AA×6`（对齐 STA 绑表扫掠节奏） |
| 6 | **WSL pts 不吃 PARENB** | 经虚拟串口/桥接开口一律 `parity="N"`；pts 是透明管道，线参由 Windows 侧对端决定 |

> 来源：references/simeter.md:35-43；references/api-contract.md:231-245

## 6. 红线（改表态前必须遵守）

1. **改之前先备份**：`GET /config`、`GET /data` 把原 `addr / version / baudrate / parity`、目标 DI 的 `value/scale` 存下来，再 `POST`；改完回读核对，联调结束按备份还原。
2. **只改本次用例要改的项**：`/config`、`/data`、`/clock` 动的是表内真实状态，会污染后续用例与别人的对档。
3. **串口独占、用完即关**：同一物理串口同一时刻一个持有者；调完 `POST /close` 立即释放；`409` 等待或换口，不硬抢（与总技能「串口独占」同一条规则）。
4. **观察先建后造**：先开 `frames`/investigations 观察，再制造目标帧，否则事件已过去。
5. **别走 v2 改表**：v2 侧只有 `simeter_frames.read`（只读）；也别绕过工作台直连物理 COM。

> 来源：references/simeter.md:1-5；references/_归档-门面v2.9.md:236-238；references/api-contract.md:223-227

## 附录 · 深水事实库（答不清时才翻，别整份读）

| 文件 | 该读哪一节 | 行数 |
| --- | --- | --- |
| `/root/.dsh/skills/ai-control-plane/references/simeter.md` | 模拟电表端点全集与自描述 | 43 |
| `/root/.dsh/skills/ai-control-plane/references/api-contract.md` | §5.1 simeter 契约 | 490 |

- 旧门面归档 `/root/.dsh/skills/ai-control-plane/references/_归档-门面v2.9.md`（257 行：v2.9 路由表、实测校准段、REQS 索引）**仅当新文档查不到时**参考。
- 铁律：事实库改动只改一处；子技能**不复制**事实库内容，避免两份说法打架。
