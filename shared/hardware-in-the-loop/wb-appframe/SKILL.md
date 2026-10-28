---
name: wb-appframe
description: 什么时候用我：手头只有一帧 hex 报文、7E 原始日志、CCO 日志或问题归档包，要离线解析报文（parse）、按知识库语义构帧做测试用例（build）、或对构好的帧做回验断言（verify）时用我。1376.2 内嵌 698/645 自动递归（典型 1103 并发抄表），全程不需要启动工作台 8790、不需要解析网关 8700、不需要 DLL / token / 串口。要驱动串口、烧录、观察取证、串口桥 preflight 的，用 /root/.dsh/skills/wb-serial/SKILL.md；分钟采集漏点专项分析用 mclt-collect-analysis。
argument-hint: "[任务，如 解析这帧报文 / 构一帧645读电能 / 回验构帧产物]"
metadata:
  author: reasonix
  version: 1.0.0
  applies-to: 任意工作区（<WORKBENCH_ROOT> 按序单点解析见 /root/.dsh/skills/wb-base/SKILL.md §1.1）
  source: 拆自 ai-control-plane（2026-10-28）
---

# 离线帧解析 / 构帧 / 回验（wb-appframe）

**边界**：本技能只讲**离线应用层帧三件套**（parse / build / verify）、1376.2 内嵌递归、库级 API、协议字典查询，以及排查「缺帧/缺报」时要直查的离线数据源。归别的子技能的事：串口会话、串口桥 preflight、需求级实时观察取证、CCO 日志在线监听 → `/root/.dsh/skills/wb-serial/SKILL.md`；AI 任务门面（v2 investigations/module-actions/flash-jobs）与授权 → 老门面 `/root/.dsh/skills/ai-control-plane/SKILL.md`（只读）；分钟采集 11E4/11E3/时钟偏移专项 → `mclt-collect-analysis` 技能。

## 1. 什么时候必须离线（先判定，不要默认起工作台）

| 手头有什么 | 走哪条路 | 说明 |
| --- | --- | --- |
| 一帧 hex 报文要解释字段 | 本技能 §2 `parse` | 纯 Python 库，直出 JSON |
| 按帧格式造一帧测试用例（TDD） | 本技能 §2 `build` | 只算字节，不触串口 |
| 构好帧要断言字段是否符合意图 | 本技能 §2 `verify` | `verified=false` 时看 `diff` |
| 7E 原始日志 / CCO 日志 / xlsx / 问题归档包，查「某时段缺数据」 | 本技能 §7 离线数据源 | 直查 sqlite/JSONL/日志，不经 HTTP |
| 分钟采集缺报/11E4/11E3/时钟偏移专项 | `mclt-collect-analysis` 技能 | 本技能只在它不可用时回退 §7 |
| 要开串口、发指令、烧录、观察取证 | `/root/.dsh/skills/wb-serial/SKILL.md` | 属在线档，别在本技能里找 |

- **覆盖范围**：应用层帧 = **1376.2（内嵌 698/645 自动递归解出，典型如 1103 并发抄表 F1H-F1）、698.45、645-2007**。GW 封装 / 双模 / 网络层帧**不在本档**（走在线全功能档）。
- 本档**不启工作台 8790、不启解析网关 8700、不需要 DLL / token / 串口**：纯 Python 解析库 `libs/parser_lib` 直用，JSON 打到 stdout。

> 来源：SKILL.md:67-78

## 2. parse / build / verify 三件套（命令可复制）

入口脚本 `<WORKBENCH_ROOT>/tools/scripts/appframe.py`，三个子命令。

```bash
# 1) 解析：hex → JSON（自动嗅探；1376.2 内嵌 645/698 进 frame.nested）
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py parse --hex "68 12 34 ..."
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py parse --hex "<错帧>" --protocol 645  # 指定=强解+warnings

# 2) 构帧：语义参数 → 帧 hex（1376.2 透传 adapter_10376.build_frame_json 全量契约）
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py build --protocol 645 \
  --params '{"addr":"123456789012","control":"11","di":"00010000"}'
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py build --protocol 698.45 \
  --params '{"addr":"05353781090030","ca":"00","oad":"02010200"}'
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py build --protocol 1376.2 \
  --params '{"afn":"F1","fn":1,"data":{"raw":"<645/698帧hex，1103包裹场景>"}}'

# 3) 回验：解析回验 + 意图字段比对（构帧产物 TDD 断言依据；verified=false 时看 diff）
python3 <WORKBENCH_ROOT>/tools/scripts/appframe.py verify --hex "68 ..." \
  --expect '{"地址域":"123456789012"}'
```

### 2.0 三个必知口径（构帧产物的「看起来不对」多半出在这里）

- **645 构帧产物是线上转义形态**：`build --protocol 645` 的 `length` 是**转义后**字节数，可能 **> 12+L**，**别拿 `length` 当 L 域**。实测 `{"addr":"123456789012","control":"11","di":"00010000"}` → `frame_hex="68123456789012681104333334331B6816"`、**`length=17`**，而 **L 域仍是 `04`**（逻辑 16B）：控制码到 CS 之间的 `0x68`/`0x1B`/`0x16` 前都会加 `1B`（**CS 字节也算**，这里 CS=0x68 → `1B 68`）；`parse` 会自动反转义，回解不受影响。
- **`--expect` 的合法键名 = `parse` 输出里的 `fields[].name`（中文）**：如 `地址域`/`控制码`/`长度域`/`校验和CS`；数据项名在 `items[].name`（如 `(当前)正向有功总电能`），内嵌帧写 `nested[0].<字段名>`。**写错名字不报错**，只静默进 `diff.missing`（实测写 `"address"` → `missing:[{"name":"address"}]`、`verified=false`、`exit=1`）——与 §5「静默不匹配」同源。
- **645 的 CS 起算点**：`CS = Σ(第一个 0x68 起 … CS 前一字节) mod 256`（含起始符/地址域/第二个 0x68/控制码/长度/数据域，**不是从控制码起算**）。起算点算错 → 判 `unrecognized`；此时**别顺手加 `--protocol 645` 蒙过去**：强解会把 CS 错**掩盖成 `warnings`**（见 §2.1），断言就失效了。

> 来源：validation-20261028/F6（T2 实机：`length=17` vs L 域 `04`、CS `1B 68` 转义；`"address"` 静默进 `missing`；CS 从第一个 `0x68` 起算）

### 2.1 双模式容错（决定「解不出来」还是「带 warnings 强解」）

| 模式 | 触发 | 行为 |
| --- | --- | --- |
| 自动嗅探（不指定 `--protocol`） | 默认 | **严格**：校验和参与打分；识别不了输出 `unrecognized` + 各协议得分 + 建议指定协议重试，**不硬解** |
| 指定协议（`--protocol 645`） | 显式 | **宽容**：**允许错误帧**，强制解析；CS/FCS 校验失败以 `warnings` 表达 |

### 2.2 退出码（写脚本断言用）

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功（`verify` 还需 `verified:true`） |
| `1` | 业务失败（JSON 内 `error` / `verified:false`，含「无法识别」） |
| `2` | 用法错误 |

> 来源：SKILL.md:80-105

## 3. 1376.2 内嵌 698/645 递归：注意点

- **一层入口、递归内嵌**：`parse` 对 1376.2 自动把内嵌的 645/698 帧解到 `frame.nested`，不用手工切内层 hex（SKILL.md:81）。
- **构帧时内层帧走 `data.raw`**：1376.2 的 `build` 用 `{"afn":"F1","fn":1,"data":{"raw":"<645/698帧hex>"}}`，即**先把内层帧构好/取到，再作为原样字节塞进 1376.2 的 DATA 单元**（SKILL.md:90-91）；这也是 1103 并发抄表包裹场景的写法。
- **AFN 与 Fn 的取值范围有硬约束**：`AFN=06` 只支持 `F1`-`F5`，写 `06/F230` 会 422（helpers.md:27）；`AFN=10/F230` 实测可构出 15B（helpers.md:26-27）。
- **`afn` 记法坑（最容易静默不匹配）**：`afn` 字符串按 **2 位 hex**（协议记法 `10H` 就写 `"10"`）；数值按**原始字节值**（`0x10=16`，写成 `10` 就变成 `0x0A`，**静默不匹配**）。`fn` 写 `"F2"`/`"F230"`/十进制都可以，expect 与 send 已同口径归一（SKILL.md:146-149）。
- 内层帧必须自成完整帧：它是原样透传的字节段，截断/补位都会让下游解析失败（见 §5「帧截断」）。

## 4. 库级 API：`libs/parser_lib/facade.py`

在 Python 脚本里直接 import，不经 `appframe.py`：

```bash
PYTHONPATH=<WORKBENCH_ROOT>/libs python3 -c "
from parser_lib.facade import decode, build, verify
print(decode('68 12 34 ...'))"
```

- 三个函数与三个子命令一一对应：`decode` / `build` / `verify`（SKILL.md:100-102）。
- 单测样例（含 1103 并发抄表构帧样本）：`<WORKBENCH_ROOT>/libs/parser_lib/test_facade.py`——写新断言前先照着它抄（SKILL.md:101-102）。
- 启动器已自动注入 `sys.path`；只有裸脚本/裸 `python -c` 才需要显式 `PYTHONPATH=libs`（SKILL.md:78）。

## 5. 常见坑

| 坑 | 现象 | 处理 |
| --- | --- | --- |
| **编码/记法**（`afn`） | 期望 `0x10` 却匹配到 `0x0A`，静默不匹配 | `afn` 一律 2 位 hex 字符串；`fn` 见 §3 |
| **默认严格不硬解** | 输出 `unrecognized` + 各协议得分 | 确认协议后加 `--protocol`，或先修帧 |
| **强行解析掩盖坏帧** | `--protocol` 下 CS/FCS 错只落 `warnings`，字段可能不可信 | 断言前先看 `warnings` 是否为空 |
| **透传层级搞错** | 把 645 帧当 1376.2 直接 `build`，或反过来 | 内层帧先单独构好，再作 `data.raw` |
| **帧截断/长度不足** | 内嵌帧解不出 `nested`、尾部字段缺失 | 内层帧要完整（含校验和），别截半帧塞进 DATA |
| **同名字段不同源** | 与 8790 `POST /api/listener/parse`（net48 DLL 深度解析）结果不一致 | 两者**口径不同源**，做对拍时才一起用（SKILL.md:103-104） |

> 来源：SKILL.md:73-77、SKILL.md:83、SKILL.md:103-104、SKILL.md:146-149、helpers.md:26-27

## 6. 协议字典查询（`/api/dict`，只读、免鉴权）

需要工作台在线（8790，loopback 免 token）；纯离线无工作台时直接读数据源 JSON（见本节末）。

```bash
curl http://127.0.0.1:8790/api/dict                    # 五本字典清单（id/名称/条数/来源路径）
curl "http://127.0.0.1:8790/api/dict/oad?q=电压"       # 698.45 OAD
curl "http://127.0.0.1:8790/api/dict/di?q=..."         # 645-2007 DI
curl "http://127.0.0.1:8790/api/dict/afn-fn?q=06"      # 1376.2 AFN/Fn 语义
curl "http://127.0.0.1:8790/api/dict/rules?q=<事件名>" # loghooks 事件规则
curl "http://127.0.0.1:8790/api/dict/cases?q=..."      # 检测用例库（REQS-0025）
```

| 端点 | 返回要点 |
| --- | --- |
| `GET /api/dict` | `[{id: oad\|di\|afn-fn\|rules\|cases, name, count, path, desc}]` |
| `GET /api/dict/oad?q=` / `/di?q=` | 698.45 OAD / 645-2007 DI（模糊过滤键/名称/描述） |
| `GET /api/dict/afn-fn?q=` | 1376.2 AFN/Fn（`{items, fn_count, source, note}`） |
| `GET /api/dict/rules?q=` | loghooks 规则（`{files:[{file,count,entries}]}`） |
| `GET /api/dict/cases?category=&type=&q=` | 检测用例库：`{count, declared_total:269, categories, items}`，`type=case\|param_table` |
| `GET /api/dict/cases/{entry_id}` | 单条用例/参数表行（404 不存在），字段含 purpose/frames/steps/criteria/source |

- `?q=` 是**模糊过滤**（对条目 JSON 全文做小写包含匹配）。
- 数据**直接来自** `libs/parser_lib/adapters/*/metadata/*.json`、`libs/loghooks/rules/`、`libs/case_library/data/cases.json`，**改 JSON 即生效**（无拷贝层）→ 无工作台时直接读这些文件等价。
- `declared_total=269` 是蒸馏原文「双模通信检测条目体系共 269 项」的**体系宣称值**；`count` 是库内**实枚举条目**（237 检测项 + 42 参数表行 = 279）。**两者口径不同、各有出处，不相等属预期**。
- observation 的 `loghook_rule.rule_id` 从 `/api/dict/rules` 查（在线档用，见 wb-serial）。

> 来源：api-contract.md:409-422、operation-guide.md:453-465、helpers.md:6-19

## 7. 离线数据源速查（缺帧/缺报直查，不依赖 HTTP）

### 7.1 问题归档必须带什么（缺了会怎样）

| 必带数据源 | 路径（打包布局） | 缺了会怎样 |
| --- | --- | --- |
| **侦听台索引库** | `.build_plain/apps/listener/runtime/indexes/idx-<时间戳>-<hash>.sqlite3`（每采集会话一个，`catalog.json` 一并带上） | 分钟分析缺权威源，只能从 7E 原文重新解析/重建索引 |
| **侦听台原始日志** | `.build_plain/data/logs/侦听台/devtty*_*_自动保存.txt` | 无法回查帧原文（索引库的原料） |
| **模拟集中器库** | `.build_plain/data/listener_13762.sqlite`（含 `.wal`/`.shm`） | 06F230 主动上报/查询快照缺失 |
| **simcon 会话帧** | `.build_plain/data/logs/simcon/sc-*.jsonl` | 1376.2 收发双向记录缺失 |
| **CCO 模块日志** | `.build_plain/data/logs/模块/cco/*.log` | **发送侧真相**缺失，判定不了「真没发 vs 发了没抓到」 |
| 页面导出 | 页面报表 xlsx（如分钟采集缺表） | 还原页面口径必需 |

- 归档包**至少含 索引库 + CCO 日志 + 侦听台原始日志**三件。索引库缺位时必须对原始日志重建索引（`POST /api/listener/logs/open`，属在线档），时间成本显著上升。
- `.build_plain/` 是打包布局根；开发树去掉前缀即 `apps/...`、`data/...`。
- **API 优先**：结构化库查询（分钟分桶 / 06H 上报历史 / 查询快照）优先走控制面 `GET /api/ai/v1/listener/minute-periods`（scope `evidence:read`）、`GET /api/ai/v1/simcon/store/events|snapshots[/{id}]`（scope `simcon:read`）。本节的离线直查只用于：① 原始日志 / CCO grep；② API 之外的临时自定义 SQL 核对（注意 `time_seconds` 是毫秒、`freeze_time` 格式等坑）。

### 7.2 排查前置：先确认采集链路在线

**任何「某时段缺数据」结论之前，先确认该时段链路在线**，否则会把「链路断线无数据」误判成「漏报/丢帧」。

```bash
# CCO 日志中找「串口会话打开/关闭」事件（发送侧链路状态）
grep -aE "串口会话打开|串口会话关闭|串口关闭" .build_plain/data/logs/模块/cco/*.log
# 若时段内无任何帧（索引库/日志库全空），多半是链路断，不是漏
```

- 典型：11:16:19 串口关闭 → 14:09:36 重开，中间 12:00~14:00 全无数据，是**链路断线**不是缺报。

### 7.3 数据源全景

| 数据源 | 路径 | 存什么 | 排查用途 |
| --- | --- | --- | --- |
| 侦听台索引库 | `.build_plain/apps/listener/runtime/indexes/idx-<时间戳>-<hash>.sqlite3` | `frames` + `minute_reports` | **分钟分析数据源（权威）** |
| 侦听台原始日志 | `.build_plain/data/logs/侦听台/devtty*_*_自动保存.txt` | 7E HPLC 帧原文 | 索引库的原料，回查帧原文 |
| 模拟集中器库 | `.build_plain/data/listener_13762.sqlite` | `frame_log` + `report_event` + `report_meter_data` + `query_snapshot*` | 06F230 主动上报 / 下发查询快照（记录面不全） |
| simcon 会话帧 | `.build_plain/data/logs/simcon/sc-*.jsonl` | 1376.2 帧 JSONL | 会话分段记录（收发双向） |
| CCO 模块日志 | `.build_plain/data/logs/模块/cco/*.log` | 固件运行日志（含 06F230/11e4/11e3 帧 hex） | **发送侧真相** |

### 7.4 侦听台索引库表结构

```bash
ls .build_plain/apps/listener/runtime/indexes/idx-*.sqlite3   # 每个采集会话一个
```

| `frames` 列 | 含义 |
| --- | --- |
| `id` / `sequence` / `log_time` | 帧主键 / 序号 / 时间 |
| `raw_hex` / `summary_json` / `parse_error` | 帧原文 / 解析结果 / 解析错误 |
| `nid` / `frm_type` / `app_id` / `msg_seq` | 网络标识 / 帧类型 / 应用标识 / 报文序号 |
| `meter_addrs` / `sta_tei` | 电表地址集合 / STA TEI |
| `flow_dir` / `ack_peer` | 收发方向 / ACK 对端 |

| `minute_reports` 列 | 含义 |
| --- | --- |
| `frame_id` / `log_time` / `time_seconds` | 关联帧 / 记录时间 / 上报时刻（⚠ 列名误导，实际存**绝对毫秒**） |
| `cco_tei` / `station_key` / `source_mac` | CCO TEI / **STA 唯一键（电表标识）** / 源 MAC |
| `task_no` / `protocol_type` / `meter_type` | 任务号 / 协议类型 / 表计类型 |
| `response_result` | 应答结果 |
| `freeze_time` | **冻结时刻（权威归属）**，格式 `YYYY-MM-DD HH:MM:SS` |
| `report_count` / `data_length` / `application_error` | 上报次数 / 数据长度 / 应用层错误 |

```bash
# 某冻结周期实际采集（权威）：该周期应到多少 STA、缺谁
# freeze_time 格式 YYYY-MM-DD HH:MM:SS；用 LIKE 前缀避免秒级精度差异
sqlite3 idx-*.sqlite3 \
  "SELECT station_key, freeze_time FROM minute_reports WHERE freeze_time LIKE '2026-08-31 14:22%';"

# 页面口径核对：按上报时刻分桶（与页面一致，会含迟报）
# ⚠ time_seconds 实际是毫秒；period_ms = 分钟数×60000，2 分钟周期 = 120000
sqlite3 idx-*.sqlite3 \
  "SELECT time_seconds/120000 AS bucket_2min, COUNT(DISTINCT station_key) AS sta_cnt
   FROM minute_reports GROUP BY bucket_2min;"
```

### 7.5 模拟集中器库 / simcon JSONL / CCO 日志

```bash
ls -la .build_plain/data/listener_13762.sqlite*   # WAL 模式：同目录 .wal/.shm，读前先 checkpoint
sqlite3 .build_plain/data/listener_13762.sqlite ".schema frame_log"

ls .build_plain/data/logs/simcon/sc-*.jsonl
jq -r 'select(.dir=="tx") | [.ts,.afn,.fn,.frame_hex] | @tsv' sc-2026*.jsonl   # 只看下发

ls .build_plain/data/logs/模块/cco/*.log
grep -aiE "06201c01" *.log   # 06F230 采集上报（详见 wb-serial / cco-log 判读要点）
grep -ai  "11e4"       *.log # 11E4 主动上报通道
grep -ai  "11e3"       *.log # 11E3 补采指令
```

- `frame_log`：收发双向帧（`dir`=tx/rx，`afn`/`fn`/`updown`=up/down，`frame_hex`，`parsed`，`day` 按天滚动保留 5 天）。
- `report_event`：06H 主动上报事件（`event_type`：F1 从节点信息 / F3 工况变动 / F4 设备类型 / F5 事件）。
- `report_meter_data`：06H F2 抄表数据（`seq_no` / `proto_type` / `uplink_sec` / `payload_hex` / `payload_json`）。
- `query_snapshot` / `query_snapshot_item`：下发查询临时快照（`mode`=manual/auto，`status`=running/done/partial/error）。
- **记录面不全属正常**：该库只落 06H 主动上报与查询快照；06F230 主动上报帧本身在 `frame_log` 完整、但解析明细只在 `report_*` 表，丢失明细不代表丢帧。
- simcon JSONL 每行：`seq`、`ts`（ISO 时间）、`dir`(tx/rx)、`kind`、`run_id`、`frame_hex`、`afn`、`fn`、`updown`(up/down)、`parsed`（1376.2 解析对象）。

### 7.6 组合排查参考链（多端交叉验证）

1. **先还原页面口径**：确认页面分桶键（默认按上报时刻分桶）。
2. **冻结时刻做权威核对**：`minute_reports.freeze_time` 统计该周期实到（见 §7.4）。
3. **发送侧 ↔ 接收侧交叉**：目标 STA 在 CCO 日志有 06F230 → CCO 发了，再查侦听台索引，无 = 接收侧丢帧；CCO 无 06F230 但有 11e3 补采 → 弱信号节点靠补采才上报（发送侧慢）。
4. **排除链路断线时段**：见 §7.2。

> 结论速记：**CCO 发了 + 索引没有 = 接收侧丢（真缺）；CCO 没发 = 发送侧问题；链路断 = 非漏**。

> 来源：references/offline-analysis.md:1-144

## 8. 路径根与交叉引用

- 命令里的 `<WORKBENCH_ROOT>` = **工作台仓库根**，解析规则（环境变量 → `~/.config/workbench/repo-root` → 向上探测 `apps/workbench`）见 `/root/.dsh/skills/wb-base/SKILL.md` §1.1；**解析不到时先问用户，不要凭记忆猜路径**。
- 要驱动串口 / 串口桥 preflight / 实时观察 / CCO 在线监听 → `/root/.dsh/skills/wb-serial/SKILL.md`。
- 路径根解析、AI 任务门面 v2、授权签发、证据分级 → `/root/.dsh/skills/wb-base/SKILL.md`
- 要知道「这次改的是哪个 endpoint / 哪个前缀」的契约口径 → `/root/.dsh/skills/ai-control-plane/SKILL.md`（老门面，迁移期只读，勿改）
- 与在线档的关系：真实下发/串口/烧录/取证仍走在线档；本技能只保证「帧本身」正确。

> 来源：SKILL.md:12-28、SKILL.md:106-121


---

## 附录 · 深水事实库（事实来源，按节读，不复制）

本技能只讲**怎么做**。精确字段、全部端点、全流程手册在入口技能的事实库里，**只有本文答不清或要核对字段时才翻对应小节**，不要整份读：

| 文件 | 该读哪一节 | 行数 |
|---|---|---|
| /root/.dsh/skills/ai-control-plane/references/offline-analysis.md | 离线归档解析、SQL、数据源全景 | 145 |
| /root/.dsh/skills/ai-control-plane/references/helpers.md | 构帧约束与 8790 预检等助手 | 47 |
| /root/.dsh/skills/ai-control-plane/references/api-contract.md | §8 协议字典 /api/dict | 491 |

- 旧门面归档（v2.9 路由表、实测校准段、REQS 编号索引）：/root/.dsh/skills/ai-control-plane/references/_归档-门面v2.9.md（257 行，**仅当新文档查不到时**参考）

> 铁律：事实库里改动只改一处；子技能里**不复制**事实库内容，避免两份说法打架。
