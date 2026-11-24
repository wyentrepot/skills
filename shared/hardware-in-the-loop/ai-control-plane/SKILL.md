---
name: ai-control-plane
description: 工作台技能入口：按需加载子技能。覆盖接入/授权/证据/错误码、固件烧录、侦听台、模拟电表、模拟集中器、离线帧工具、串口桥与用例回归；本文件只做目录与路由，不装内容——单域任务只加载一个 wb-* 子技能，跨域任务按 §2 任务旅程链按序加载。
argument-hint: "[task, e.g. 解析这帧报文 / 烧录固件 / 查已解析帧 / 调测模拟电表 / 跑验证用例 / 排查采集漏点]"
metadata:
  author: reasonix
  version: "4.0.0"
  applies-to: 任意工作区（<WORKBENCH_ROOT> 按序单点解析见 wb-base §1.1）
  source: 本文件只是入口，细节在各 wb-* 子技能（技能名即索引名，索引根见 wb-base §1.1）；红线与硬前提唯一来源是 wb-base，本文件不复制
---

# AI 控制面（ai-control-plane）· 技能入口

**先判定在线还是离线（只判一次，判完直接进子技能）**：
1. **离线**：手头只有帧/日志/文件，且不需要驱动工作台 → 解析/构帧/回验进 `wb-appframe`；分钟采集漏点/11E4/11E3/时钟偏移走 `mclt-collect-analysis` 专项技能。
2. **在线**：要驱动工作台（串口、烧录、观察取证、验证、模拟表、用例回归）→ 单域任务按 §1 表选一个子技能；跨域任务按 §2 链按序加载。
3. **拿不准后端有什么**：先让工作台报一次能力清单与源健康（做法见 wb-base §3.1），再回到第 2 步选路。

## §1 子技能目录（8 个，技能名即索引名，一一对应；校验见 tools/scripts/verify_skills.py）

| 子技能 | 一句话能力 | 何时加载（判定条件） |
| --- | --- | --- |
| wb-base | 共享基座：接入·授权·证据·错误码 | 任何在线任务开始前；或遇到 401/403/404/409/422/503、要授权凭据、要定证据口径 |
| wb-flash | 固件烧录与结果判定 | 要烧固件、查烧录结果、判断 `succeeded` 是否等于验证通过 |
| wb-listener | 侦听台索引、帧查询、通信流追踪 | 要查已解析帧、追踪一轮业务、给日志建索引、定位分钟采集漏点 |
| wb-simeter | 模拟电表 645/698 从站调测 | 要调测模拟电表、验证 645/698 应答、与模拟集中器对档联调 |
| wb-simcon | 模拟集中器验证/单步/并发抄表 | 要跑验证任务、单步下发、感知主动上报、并发抄表或查档案 |
| wb-appframe | 应用层帧解析/构帧/回验（离线） | 手头只有一帧报文或一组语义参数，且明确不启工作台 |
| wb-serial | 串口桥 preflight 与模块串口会话 | 要开任何串口、发串口指令，或烧录/侦听/验证之前的开串口环节 |
| wb-casetest | 黑盒用例执行：case_run.py · 四态结论 · 用例库盘点 | 用户**明确指派**黑盒测试/跑用例/回归时，才跑用例、补用例、标可测性（未明确指派不加载） |

## §1.5 前置设施：Windows 宿主控制面（8766，不是子技能）

串口桥 / 解析网关 8700 / 海思诊断服务 8765 的**看板与开关**都在 Windows 侧常驻服务 8766 上
（`tools/win_host/`，计划任务 `FC-Wsl-Control`）。所有"在线"任务开工前先看它一眼：

```bash
HOST=$(ip route show default | awk '{print $3}'); TOKEN=$(cat /mnt/c/Users/*/.wsl-control/token | tr -d '\r\n')
curl -s -H "X-Host-Token: $TOKEN" http://$HOST:8766/api/v1/status   # 或直接开 http://127.0.0.1:8766/
```

- 看板：`http://127.0.0.1:8766/`（Windows 本机自动带令牌；WSL 打开需粘贴令牌）
- 接口与语义：`wb-base §1.4`；**usbipd 已移除**（`/api/usbipd/*` → 410），不要再 attach/detach
- 让口/接管、服务启停、自检：`/api/v1/ports/{id}/disable|enable`、`/api/v1/services/*`、`/api/v1/doctor`

## §2 任务旅程组合链（跨域任务按链按序加载，每步用完即止）

单域任务不进链；链内每一步仍是"读那个子技能 → 做完该步 → 停"，不展开任务外动作。

| 链 | 触发（用户话语特征） | 步骤（按序） |
| --- | --- | --- |
| 烧录验证链 | "烧一版固件"、"烧完确认入网/真烧成" | wb-base → wb-serial（preflight+会话）→ wb-flash（烧录判定）→ wb-listener（入网/帧证据） |
| 采集排障链 | "漏点/不入网/这轮抄表断在哪跳"、"解释某帧" | wb-base → wb-listener（查帧定位）→ wb-simcon/wb-simeter（复现或注入）→ wb-appframe 或 mclt-collect-analysis（离线深解析） |
| 用例回归链 | "黑盒测试"、"跑一遍用例"、"搭回归" | wb-base → wb-casetest（给入参跑 case_run → 拿四态结论）→ wb-simcon/wb-listener（过程与帧证据） |

## §3 硬前提与红线（唯一来源：wb-base，此处不复制）

- 路径根解析 → wb-base §1.1；授权（对话授权后可自签 grant）→ wb-base §2；开串口前 preflight → wb-serial。
- 行为红线 8 条完整表述 → wb-base §6.2；契约检查清单 → wb-base §6.3。
- 本文件如与 wb-base 冲突，以 wb-base 为准；一致性由 `tools/scripts/verify_skills.py` 把关。
