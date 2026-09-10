# 网络层诊断知识包（network-diagnostics）

> REQS-0025 G3/D1。组网类问题（入网/离网/冲突/心跳/信标/CSMA）的诊断知识：状态机、门限、
> 故障特征→根因映射。口径与 `libs/network_assert`（断言规则库）和侦听台评估 B 类规则一致；
> 事实来源：蒸馏库 `CCO实现逻辑/07-NWK`、`08-MAC`、`13-文档与代码差异记录`、`06_测试用例`（国网口径，南网未引用）。
> 本篇是**判读知识**，取证动作仍按 SKILL.md 路由表走 API。

## 0. 取证路径（先证据后判定）

1. **L1 结论（低 token 首选）**：`GET /api/listener/network/digest`（workbench 8790；独立版 8765 用 `/api/network/digest`）≤4KB——`verdict` 一句话判定 + `level`(alarm/watch/normal) + 异常清单（类型/计数/首末时间/人话示例）+ 网络概要 + 自适应时间桶计数（桶内含异常数，用于定点定位时段）。
2. **L2 事件流**：`GET /api/listener/network/events?level=alarm,watch&start_time=&end_time=&limit=`——`level` 过滤降噪（alarm 异常 / watch 关注 / normal 常规，缺省全量）；事件带 `human`（TEI→表号人话摘要）、`src_label`/`dst_label` 翻译列，`fields` 仍带全量解析字段（如 assoc_cnf 的 `rslt`/`retry_time_ms`/`proxy_tei`）。锁定时段用 digest 返回的桶窗（12 字符毫秒精度）。
3. **L3 单帧粗略解析**：`GET /api/listener/network/events/{frame_id}/brief` ≤2KB——分层中文摘要（GW 封装/MAC 头/管理表字段）+ 事件人话 + warnings；点击排查时按需调用，不必整页预载。
4. **L4 信标/评估**：`/api/listener/network/beacons`（四时段重建 `fields.periods_ms`）、`/api/listener/network/assessment`（三级判级）、`/api/listener/network/status`（≤1KB 快照，仅要评级时用）。
5. **判级口径**：`libs/network_assert/rules/*.json`（8 条断言声明，含出处）；门限摘要见 §2。digest 的异常分级是服务层轻量内联版（assoc_cnf rslt∉{0,0xA} / 离网 / NID·信道冲突 / 路由错误 / BPCS 失败=alarm；代理变更 / 网间协调 / 成功率<90%=watch），**门限出处与本包 §2 同源**。
6. 用例背景查 `/api/dict/cases`（269 项检测体系）。

## 1. 组网状态机与关联结果码速查

**站点状态机**（`inc/nwk/sta.h:74-80`）：

```
UNASSOC ──关联确认成功──► ONNET ──第1个心跳周期无心跳──► OFFLINE
   ▲                                                      │连续4个心跳周期无心跳
   └──────────重新关联成功────────────────────────────── WAITON ◄─┘（发离网指示，10s 后删除）
```

**关联结果码 rslt**（`sta.h:46-63`，关联确认 table70 携带）：

| 码 | 枚举 | 含义 | 诊断指向 |
| --- | --- | --- | --- |
| 0 | SUCCESS | 关联成功 | — |
| 1 | OUTOFLIST | 不在白名单 | 档案 MAC 与 STA 实际不符 / 白名单池未装载完（上电分批 `laddPollInit`）；退避 40/60/600s 分档 |
| 2 | INBLACKLIST | 在黑名单 | 黑名单按分钟刷新（`BlackListTimeFlush`） |
| 3 | STANUM_LIMIT | 站点超上限 | `STA_NUM_MAX=1023` / TEI 空闲池耗尽 |
| 4 | WLIST_NOSET | 未设白名单 | 自上而下（有档案）模式必须先设白名单 |
| A | DUP_SUCCESS | 再次关联成功 | 重入网保号（`readd`），**非故障** |
| B | TRY_SUB_SITE | 试图以自己的子站点为代理 | 拓扑异常 |
| C | LOOP_EXIST | 存在环路 | 拓扑/中继异常 |
| E | RFPCO_LIMIT | RF 代理超限 | `rfProxyLimitEn` 代理总数 / RF 跳数超限 |
| F | UNKNOWN | 其他（含全 00/99/FF 特殊地址禁入网） | 地址非法或未分类原因 |

**拒绝退避档位**（`nwk_reject_list.c:115-119` + `cac.h:173-178`）：上电 <121s 防洪泛档（40s）→ 121~1800s（60s）→ >1800s（600s）；开关关闭时按 MAC 指数退避 16×2^cnt 秒上限 6 次。

## 2. 门限速查表（与 libs/network_assert 同口径）

| 门限 | 值 | 规则 id | 出处 |
| --- | --- | --- | --- |
| 关联拒绝退避分档 | 40/60/600s，边界 121s/1800s | `nwk.assoc_reject.backoff_tiers` | 07 §1.4 |
| 心跳缺失离网 | 第 1 周期 OFFLINE；连续 4 周期 WAITON+离网指示；10s 后删除 | `nwk.heartbeat.offline_4cycles` | 07 §5.4 |
| 心跳周期 | 路由周期×2（≤20 站）/×4（>20 站） | `nwk.heartbeat.period_ratio` | 07 §5.4 link.c:390 |
| 信标周期合法域 | 协议 1~10s；评估参数口径 500ms~120s（实测 14878ms） | `nwk.beacon.period_domain` | 06 §7.3 + 评估 |
| 路由周期 | <20 站 60s；否则 ceil(n/20)×50s，钳位 [50,720]s | `nwk.route.period_adaptive` | 07 §6.4 |
| CSMA 时隙占用 | >60% 降级、>80% 故障（占比=CSMA 时隙/信标周期） | `nwk.csma.occupancy_two_tier` | 评估 B 档 |
| 通信成功率三级 | ≥98% 健康 / 90~98 亚健康 / <90 故障；离线率 ≤2 / 2~10 / >10% | `nwk.comm_success_rate.three_tier` | 评估 A 档 |
| 冲突仲裁时序 | NID：307ms/30min；RF：20.7s/30min（协调帧触发一律 307ms/20.7s）；t2=5min 解除；切换 100s+确认 102s | `nwk.conflict.arbitration_timing` | 07 §7 |
| STA 主动离网口径 | 两路由周期无信标 / 连续 4 路由周期成功率 0 / 层级>15 / 组网序列号变化 / 收到离线指示 | — | 06 §2.5.2.11 |

## 3. 信标/时隙速查

- **中央信标**：table38 头（type=2、允许关联、组网序列号 NWKFormNo、CCO MAC）→ 条目顺序 47 站点能力 → 48 路由参数 → 54 无线路由 → 万年历 → 50 时隙分配 → 49 频段变更 → 55 无线频道变更；载荷尾 BPCS 32bit CRC。
- **四时段**：信标 / TDMA / CSMA / 绑定CSMA（table50）；CSMA 时段提前 2ms 结束，TDMA 时隙提前 400us，信标发送延迟 1200us；CSMAStartNTB=(信标+TDMA 时长)×25000。
- **NTB**：单位 0.04us（25MHz）；CIFS 载波 400us / 无线 800us；RIFS 2300us；EIFS 协议 20/70ms（工程 /12、/8 抗前导误检）。
- **网间协调帧**：1900ms 一个序号，CSMA 空闲片竞争发送；带宽退避 = 重叠量+对方时长+20ms。
- **频段/频道变更**：剩余时间 >100ms 才在信标宣告（table49/55），全网同步切换。
- **编址/路由**：TEI 12bit（0 非法、1=CCO、2..1023 站点、4095 广播）；层级上限 15；每站路由表 4 个下一跳（rte[0] 最新）；RouteError ≤15 个不可达 TEI，仅解析不联动删路由；代理广播判重四要素 = 源 MAC+MSDU 序号+重启次数（128 项哈希环形表）。

## 4. 故障特征→根因映射表

> 用法：按症状找到行 → 按「先查」列去事件流/评估取证据 → 命中根因方向后引用「依据」列的出处/规则 id 复核。

| # | 症状 | 先查（证据） | 根因方向 | 依据 |
| --- | --- | --- | --- | --- |
| 1 | 无法入网·被拒 rslt=1 | assoc_cnf.rslt、retry_time_ms | 档案地址与 STA 实际 MAC 不符；白名单池上电分批装载未完成 | 07 §1；`nwk.assoc_reject.backoff_tiers` |
| 2 | 无法入网·rslt=4 | CCO 白名单标志/档案下发 | 自上而下模式未设白名单即开放入网 | 07 §1.4 cac.c:87 |
| 3 | 无法入网·rslt=3 | 在网站点计数、TEI 池 | 1023 上限或空闲池耗尽（TEI 未回收） | 07 §2 |
| 4 | 无法入网·rslt=2 | 黑名单事件 | STA 曾被拉黑，按分钟刷新等待/移除 | 07 §2.4 |
| 5 | 无法入网·rslt=E | RF 代理计数/跳数 | rfProxyLimitEn 代理总数或 RF 级联超限 | 07 §1.4 |
| 6 | 无法入网·rslt=B/C | 拓扑/中继事件 | 以子站点为代理或环路，选代理被拒 | 07 §3.4 |
| 7 | 反复重关联（入网后周期性掉） | leave_ind 事件、心跳计数 | 心跳 4 周期判离网；台区心跳转发缺失（代理变更请求视作心跳补救） | 07 §5；`nwk.heartbeat.offline_4cycles` |
| 8 | 反复重关联·成批发生 | 信标 NWKFormNo | 组网序列号变化（CCO 重组网）→STA 集体主动离网重入 | 06 §2.5.2.11 |
| 9 | 整站离网·伴随 NID/信道事件 | conflict 组事件 | NID 冲突改 NID（307ms/30min 仲裁）或 RF 信道切换（100s 切换）期间全网迁移 | 07 §7；`nwk.conflict.arbitration_timing` |
| 10 | 整站离网·信标消失 | beacons 到达间隔 | CCO 停发信标（掉电/守护重启），按信标周期计数断档定位 | 07 §6 |
| 11 | 部分离网·链路劣化 | 通信成功率上报 | STA 连续 4 路由周期成功率 0 主动离线 | 06 §2.5.2.11；`nwk.comm_success_rate.three_tier` |
| 12 | 部分离网·信标收不到 | 信标/发现列表老化 | STA 两路由周期无信标主动离线；RF 接收率老化 5 周期 | 06 §2.5.2.11；07 §8 |
| 13 | 代理震荡 | 代理变更请求帧占比（>8% 判降级） | 信道劣化触发 table79 重选；确认在位图式/TEI 式间交替保证可靠切换 | 评估稳定性 + 07 §3 |
| 14 | 冲突频发 | rf_conflict/nid_conflict 事件、SACK 失败率 | 邻网 CCO MAC 仲裁避让反复；VCS 前导误检（工程 EIFS/12、/8） | 07 §7 + 08 §6 |
| 15 | 心跳丢失但表计在位 | 心跳位图、路由周期 | 心跳档位误判（>20 站 ×4）；PCO 子站位图 OR 汇聚缺失 | 07 §5；`nwk.heartbeat.period_ratio` |
| 16 | CSMA 拥塞 | table50 四时段占比 | 占比 >60%/80% 两级判级；业务洪峰或时隙规划失衡；minBE=4 退避重传加剧 | 08 §1-2；`nwk.csma.occupancy_two_tier` |
| 17 | 通信成功率低 | 评估成功率三级 | 链路质量（SNR/RSSI 一阶滤波）、重传 NB/BE 封顶（maxBE=8）仍失败 | 评估 A 档 + 08 §2 |
| 18 | 疑似广播风暴 | 重传帧计数 | 代理广播判重四要素未命中的重复帧（缓存 128 项，重启次数不同视为新帧） | 08 §8 |
| 19 | 升级/并发互扰 | 升级窗口、并发队列 | 升级期间并发上限临时压到 5；AFN=F1H 并发队列条目 5 分钟生命周期自消亡 | 13 号 #41 |
| 20 | 层级超限离网 | 代理信标条目 47 层级 | STA 层级>15 主动离线；多级代理规划失衡 | 06 §2.5.2.11 |

## 5. 已知文档-代码差异提示（13 号记录精选）

判读时以下差异容易踩坑（文档说 A，参考实现做 B）：

1. **并发抄表超时**：业务文档 60s，实现 99s（`CONC_METER_TRANS_MAX_SEC`）；队列条目 5 分钟生命周期自消亡。
2. **报文过滤缓存**：设计文档 8 帧，实现 128 项哈希环形表。
3. **VCS 前导忙**：协议 EIFS 20/70ms，实现 HPLC_EIFS/12≈1.67ms、RF_EIFS/8（抗前导误检）。
4. **CSMA 最小退避指数**：实现 minBE=4（注释"由 2 改为 4"），maxBE=8。
5. **掉电第一阶段**：文案 80s，实现 70000ms。
6. **上电波特率探测**：实现仅 9600E/115200N/115200E 三档轮换。
7. **信标类型值**：定界符类型 0=信标帧（MAC 帧控制），table38_stuff_type 填 2 表示"中央信标"——两个"类型"不是一回事。
8. **路由修复不闭环**：RouteReply/RouteAck 已实现，RouteError 仅解析不联动删路由；LinkConfirmRequest 构帧未发送。

## 6. 与本仓资产的关系

- `libs/network_assert/`：8 条断言声明（触发/窗口/判定/阈值/出处）+ 静态校验；`evaluate()` 预留，接入 REQS-0024 事件流后生效。
- `/api/dict/cases`：269 项检测体系用例库（REQS-0025 G1），查检测条目/帧类型/判定标准。
- 组网观测页签（REQS-0024/0026）：`/api/network/*` 端点；0026 已交付 `digest`（L1 结论 ≤4KB）与 `events/{frame_id}/brief`（单帧粗解 ≤2KB）——其异常分级为服务层轻量内联版，**门限以本包 §2 与断言库为准**。
