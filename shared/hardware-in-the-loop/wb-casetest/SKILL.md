---
name: wb-casetest
description: 什么时候用我：仅在用户**明确指派**「黑盒测试 / 跑用例 / 用例回归 / 搭回归链 / 用例库盘点」时用我——在 CCO/STA/ECU 台架上以「给入参 → 跑 → 出四态结论」的零参与方式执行用例，或按知识库用例库补用例、标可测性、跑长跑。用户没明确指派时不要加载；单帧下发/构帧调试走 wb-simcon / wb-appframe，烧录走 wb-flash。
argument-hint: "[任务，例如 跑 meter_daily / 把 CCO 03H-F1 做成用例 / 盘一下本环境能测哪些用例]"
metadata:
  author: reasonix
  version: "1.1.0"
  applies-to: 有工作台（8790）+ CCO/STA 台架、且仓库内有 libs/case_runner 的工程（ZZT_SELF 现状）
  source: 2026-11-04 首批沉淀；2026-11-24 对齐 REQS-0042/0043 的真实执行载体（case_run.py + 四态 verdict），用例来源改为指索引不抄数字
---

# 黑盒用例测试：单入口执行 · 零参与 · 四态结论（wb-casetest）

**核心原则**：一条用例就是一次「给入参 → 跑 → 出结论」。从触发到出结论，**全程不需要人看屏、不需要 AI 判断、不需要补参数**。

## 0. 执行载体（先认清是哪一套）

| 层 | 东西 | 位置 |
|---|---|---|
| 声明 | 块 / 事实 / 用例 / 方案 JSON | `libs/case_runner/data/{blocks,facts,cases,case_suites}/` |
| 引擎 | 四层模型 `Case → Block → Fact → Capability` | `libs/case_runner/` |
| 入口 | CLI | `tools/scripts/case_run.py`（list/show/run/probe/check） |
| 服务 | API + UI | `/api/cases/*`（`apps/workbench/cases_api.py`） |
| 证据 | 每轮落盘 | `data/case_runs/<run_id>/result.json` |

本技能 `scripts/`（runner.py + wbclient.py + template_case.py）是 2026-11-04 的**外部兜底框架**：仅当工程里没有 `libs/case_runner` 时才用它（见 §8）。

## 1. 三步上手

```bash
python3 tools/scripts/case_run.py list --json                 # 计数：块/事实/用例/方案
python3 tools/scripts/case_run.py show meter_daily            # 步骤 + 块清单 + needs
python3 tools/scripts/case_run.py run --case meter_daily --json
python3 tools/scripts/case_run.py run --suite meter_smoke_min --timeout 600 --json
python3 tools/scripts/case_run.py probe --all --readonly --json   # 只读自检，不动台架
python3 tools/scripts/case_run.py check                       # 声明校验，problems 必须为空
```

- **唯一入参**是 `--params '{...}'`；地址参数只叫 `meter_addr`（旧名 `addr/meters` 直接退出码 3，不给兼容别名）。
- 工作台地址发现顺序：`--base-url` > 环境变量 `WORKBENCH_BASE` > `data/runtime/workbench.json` > 本机 8790。
- **加用例 = 加声明，不改引擎**：用例 JSON 用 `plan` 步骤实例化块（`id` / `block` / `params` / `on_fail`），`needs` 声明前置事实，`tags` 给分类。

## 2. 用例从哪来（指索引，别抄数字）

两个「用例库」不是一回事，别混：

| | 是什么 | 去哪查 |
|---|---|---|
| 知识库用例库 | 自家送检/厂验原始用例，按设备分（`STA/`、`CCO/`，各含 `台账/` + `能力域/`） | `/01-workfile-ai/04-obsidian/obsidian/用例库/00_总览.md` 进门 |
| 已实例化用例 | 引擎里真能跑的（当前 7 条，随批次增长） | `case_run list --cases` |

**规则：先查知识库，再落地成用例。** 不许凭记忆编判据；查不到出处的场景不写进用例库（标「库中未找到」）。
本环境能力清单与逐条可测性标注在 `reqs/0043-case-library-expansion-and-soak/CASE-BACKLOG.md`（16 块 / 8 事实 / 台架条件 / 不可测原因）——**每次补用例前先读它，别重复盘**。

筛选三问：① 被测设备本台架能替代吗？② 前置要几台设备（第二 STA / II 采 / 真实电表 → 不可测）？③ 判据要目视或破坏性（灯语 / 升级 / 掉电 / 复位）？

## 3. 四态结论（唯一判据）

| verdict | 含义 | 退出码 |
|---|---|---|
| `pass` | 全部块与断言通过 | 0 |
| `fail` | **被测对象真失败**（有应答但判据不成立） | 1 |
| `inconclusive` | **说不清**（超时无应答 / 解析不出 / 等满仍学习态） | 2 |
| `blocked` | **台架不具备**（预检不过 / 端口被占 / 缺参） | 5 |

用法/参数错误 3、声明加载失败 4。多块混合按 `fail > blocked > inconclusive > pass` 取最严重者。
**无应答绝不判 pass；`blocked` 绝不折算成 `fail`；`inconclusive` 也绝不冒充通过。**

## 4. 黑盒纪律（REQS-0042 D-1~D-4）

| 判据 | 落地 |
|---|---|
| D-1 单入口 | 只给入参 + 触发运行，没有第二步 |
| D-2 零参与 | `result.json` 的 `interventions[]` **恒空**；AI 不许中途补参、改判、盯屏看日志 |
| D-3 结论可分 | 真失败 / 台架不具备 / 说不清三者不可混（§3） |
| D-4 可复现 | 同入参 + 同台架 → 同结论；每轮落 `verdict` / `params` / `decisions[]` / `self_healed` / 时间戳 / 台架快照 |

默认输出是**报告式**：一句话结论 + 人话原因 + 证据路径，**不出现块名**；要看块 id 加 `--verbose`（D11-1/D11-2）。

常见借口 → 现实：

| 借口 | 现实 |
|---|---|
| 「就缺一个参数，我补上」 | 缺参 = `blocked` / 退出码 3。补参就是人工参与，D-2 破功 |
| 「等了 N 秒没应答，先算过吧」 | 无应答 = `inconclusive`；判 pass 就是假 PASS |
| 「blocked 就按失败报」 | 台架不具备 ≠ 被测失败，混了没法追责 |
| 「我盯一下日志再下结论」 | 结论只能来自 `result.json` 的四态 |
| 「顺手改个地址/超时试试」 | 违反零扰动铁律（§6-8），可能毁台架状态 |

## 5. 证据与长跑

- 每轮落 `data/case_runs/<run_id>/result.json`；`--keep-runs N` 默认只留最近 30 轮（当前这一轮永不删）。
- 长跑（REQS-0043 CL-5/CL-6）：≥20 轮连跑 + ≥2 小时持续，汇总轮次/结论/耗时/RSS；连续 3 轮 `blocked` 即停并报告。
- 长跑主线用 `meter_daily`（不复位）；`meter_first_join` 会复位，复位后链路恢复实测 ≈10 分钟，别串进日常回路。

## 6. 硬约束与坑

1. **整轮预算 `--timeout` 默认 600s**：超时按 `inconclusive` 收尾并写明卡在哪个块。长等待拆成多轮短窗在用例层循环，别把一个 900s 等待塞进单轮。
2. **端口被占**（`已被后端会话"模拟集中器"占用`）：`POST /api/simcon/close` 释放后重试；并发走 lease，`409 no_queue_reject` 不硬抢。
3. **工作台重启会带走 simeter 串口会话**：重开 `POST /api/simeter/open {"mapping_id":"simeter"}`。
4. **串口物理独占**：同口严格串行，不同口（simcon / cco-main / sta-main）可并行。
5. **串口桥必须先起**（Windows 侧 `serial_bridge.py windows`），否则全口不可用 → 一律 `blocked`，不要当 fail 报。
6. **台架拓扑**：`simcon(COM4) → CCO(COM12) → HPLC → STA(COM18) → 表口 → 模拟电表(COM20)`；侦听台 COM27 本环境不接。
7. **电表 645 地址与 CCO 档案地址互为 6 字节整体反转**：对外只用 `meter_addr` 一种人读口径，别在用例里手拼线序。
8. **设置类零扰动铁律**：只允许「读原值 → 写同值 → 回读」；绝不写不同配置（改地址/超时/时钟/档案都可能毁台架状态）。
9. **协议时序类坑先查知识库**：如 F230 存数库只在会话在线期累积、11E3 自主补抄约 9 分钟后才发生。排等待预算前先查证，别套记忆。
10. **1376.2 帧头 13B**（68+L2+C1+R6+AFN1+DT2）、尾 CS 1B+16：手写解析别套 698 的 HCS/FCS 2B 口径。
11. **token**：v2 门面（`/api/ai/v2/*`）本机 loopback + `WORKBENCH_LOCAL_FULL_ACCESS=1` 免 token；`/api/cases/*` 与直连面（`/api/simcon/*`、`/api/simeter/*`）本机免 token。

## 7. 红线

- 不 push 任何项目仓库；不重启工作台（除非任务明确要求）。
- 不改四层模型边界（Case/Block/Fact/Capability）：缺能力就加块，不改引擎语义。
- 判据不许硬编码送检台价值（厂商码、地址等以台架实值为准：先读参照量再比对）。
- AI 不参与执行：不在用例跑到一半时改参数、改判据、手工补一步。

## 8. 兜底：`scripts/` 老框架

工程里没有 `libs/case_runner` 时，可把 `scripts/` 复制成 `<PROJECT>/autotest/`，走 v2 verify 任务（`result:"pass"` 字符串判据、每项一份 `docs/<id>.md` 三段式标题、支持与否三档）。
**两套语义不要混用**：v2 verify 的 `pass` 只证明「帧发出去了」，≠ 四态里的 `pass`。
