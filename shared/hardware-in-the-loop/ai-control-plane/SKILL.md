---
name: ai-control-plane
description: 工作台技能入口：按需加载子技能。覆盖接入/授权/证据/错误码、固件烧录、侦听台、模拟电表、模拟集中器、离线帧工具与串口桥；本文件只做目录与路由，不装内容——每次任务按判定条件只加载一个 wb-* 子技能。
argument-hint: "[task, e.g. 解析这帧报文 / 烧录固件 / 查已解析帧 / 调测模拟电表 / 跑验证用例]"
metadata:
  author: reasonix
  version: "3.0.0"
  applies-to: 任意工作区（<WORKBENCH_ROOT> 按序单点解析见 /root/.dsh/skills/wb-base/SKILL.md §1.1）
  source: 本文件只是入口，细节在各 wb-* 子技能（/root/.dsh/skills/wb-*/SKILL.md）；旧 SKILL.md 与 references/ 迁移完成前仍是唯一在用门面
---

# AI 控制面（ai-control-plane）· 技能入口

**先判定在线还是离线（只判一次，判完直接进子技能）**：
1. **离线**：手头只有帧/日志/文件，且不需要驱动工作台 → 解析/构帧/回验进 `wb-appframe`；分钟采集漏点/11E4/11E3/时钟偏移走 `mclt-collect-analysis` 专项技能。
2. **在线**：要驱动工作台（串口、烧录、观察取证、验证、模拟表）→ 按上表选一个 wb-* 子技能，只读那一个，用完即止。
3. **拿不准后端有什么**：先让工作台报一次能力清单与源健康（做法见 wb-base §3.1），再回到第 2 步选路。

## 子技能目录（7 个，只按判定条件加载）

| 子技能 | 一句话能力 | 何时加载（判定条件） | 入口 |
| --- | --- | --- | --- |
| wb-base | 共享基座：接入·授权·证据·错误码 | 任何在线任务开始前；或遇到 401/403/404/409/422/503、要授权凭据、要定证据口径 | `/root/.dsh/skills/wb-base/SKILL.md` |
| wb-flash | 固件烧录与结果判定 | 要烧固件、查烧录结果、判断 `succeeded` 是否等于验证通过 | `/root/.dsh/skills/wb-flash/SKILL.md` |
| wb-listener | 侦听台索引、帧查询、通信流追踪 | 要查已解析帧、追踪一轮业务、给日志建索引、定位分钟采集漏点 | `/root/.dsh/skills/wb-listener/SKILL.md` |
| wb-simeter | 模拟电表 645 从站调测 | 要调测模拟电表、验证 645 应答、与模拟集中器对档联调 | `/root/.dsh/skills/wb-simeter/SKILL.md` |
| wb-simcon | 模拟集中器验证/单步/并发抄表 | 要跑验证用例、单步下发、感知主动上报、并发抄表或查档案 | `/root/.dsh/skills/wb-simcon/SKILL.md` |
| wb-appframe | 应用层帧解析/构帧/回验（离线） | 手头只有一帧报文或一组语义参数，且明确不启工作台 | `/root/.dsh/skills/wb-appframe/SKILL.md` |
| wb-serial | 串口桥 preflight 与模块串口会话 | 要开任何串口、发串口指令，或烧录/侦听/验证之前的开串口环节 | `/root/.dsh/skills/wb-serial/SKILL.md` |

## 三条硬前提（每次在线任务都成立）

- **路径根**：仓库内路径一律相对 `<WORKBENCH_ROOT>`，按序单点解析，解析不到先问用户 —— 见 `/root/.dsh/skills/wb-base/SKILL.md` §1.1。
- **开串口前先 preflight**：串口桥未就绪不许开任何串口会话 —— 见 `/root/.dsh/skills/wb-serial/SKILL.md`。
- **授权只由人签发**：AI 只使用人已签发的凭据，不自签、不扩权 —— 见 `/root/.dsh/skills/wb-base/SKILL.md` §2。

## 红线总目（完整版见 wb-base §6）

1. 授权归人、scope 最小化：只申请本次任务需要的范围。
2. 用完即止：不开任务外会话、不跑任务外验证、不做"顺手"的全流程。
3. 串口独占：同一物理串口同一时刻一个持有者，开了就关，遇冲突等待或换口，不硬抢。
4. 观察先建后造：先建观察，再制造目标事件。
5. 不可取消：烧录/验证耐心等到终态，不并发重试。
6. 常驻与停止：沙箱环境必须用受管后台任务常驻；停止进程禁用会匹配到自身的模式匹配。
