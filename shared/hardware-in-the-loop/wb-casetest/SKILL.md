---
name: wb-casetest
description: 什么时候用我：要把送检/厂验用例（非台体）做成可重复执行的自动化测试——从知识库用例库挑出本环境能测的项、写用例脚本、指定运行、串联成链路、每项产一份带支持与否/验证状态的文档。碰到"这个用例能不能自动测""帮我搭一套回归""跑一条端到端链路"时用我。单帧下发/构帧调试不归我（走 wb-simcon / wb-appframe）。
argument-hint: "[任务，例如 把 CCO 03H-F1 做成用例 / 跑 cco-afn-smoke 链 / 列一下本环境能测哪些用例]"
metadata:
  author: reasonix
  version: "1.0.0"
  applies-to: 任意有工作台（8790）+ CCO/STA 台架的工作区（WORKBENCH_LOCAL_FULL_ACCESS=1 免 token 走 v2）
  source: 2026-11-04 CCO/STA 非台体内测项自动化批次沉淀（autotest/ 框架 + 22 用例实跑）
---

# 用例自动化测试：指定运行 · 链路编排 · 逐项文档（wb-casetest）

把「知识库用例库 → 本环境可测清单 → 用例脚本 → 实跑证据 → 链路」串成一条可重复的流水线。
框架本体在 `scripts/`（runner.py + wbclient.py + template_case.py），与项目零耦合，只调工作台 HTTP。

## 0. 三步上手

```bash
# 1) 把本技能 scripts/ 复制为项目里的独立测试目录（如 <PROJECT>/autotest/）
mkdir -p <PROJECT>/autotest && cp -r scripts/* <PROJECT>/autotest/
# 2) 按 scripts/template_case.py 写 cases/<id>.py（CASE 元数据 + run(ctx)）
# 3) 显式指定才运行（无参数只列清单，不动任何串口）
cd <PROJECT>/autotest
python3 runner.py --list                  # 清单 + 支持与否 + 最近结果
python3 runner.py --case <id> [id…]       # 单个/多个
python3 runner.py --chain cco-mclt-e2e    # 链路（chains.json）
python3 runner.py --group cco-afn         # 按 tag 组
```

## 1. 测试项从哪来（非台体口径）

- **用例库**（obsidian 库 `用例库/`）＝自家送检/厂验用例：STA 339 例（台账 123~140）、CCO 241 例（台账 144~155），能力域蒸馏 141/142/143/156/157。
- **台体类**（`台体测试/117/118`）不在此列，按约排除。
- 筛选三问：① 被测设备是本环境实板/模拟器能替代的吗？② 前置要几台设备（第二 STA/II采/真实电表/水表→不可测）？③ 判据要目视/破坏性（灯语/升级/掉电/复位→不安排）？
- 输出三档：`supported=yes`（实跑）/`partial`（子集或工具链受限）/`no`（环境不具备，仍要单独出文档）。

## 2. 用例契约（照 template_case.py）

```python
CASE = {"id": "...", "title": "...", "source": "<用例库卡+行号>", "supported": "yes|partial|no",
        "supported_reason": "...", "tags": ["cco-afn"], "desc": "...", "how": "..."}
def run(ctx):
    r = ctx.verify([{"name": "s1", "send": {"afn": "03", "fn": 1, "params": {}},
                     "expect": {"afn": "03", "fn": 1}, "expect_timeout": 8}])
    return True, "证据一句话"
```

ctx 能力：`verify(steps)`（v2 任务，自动等 lease + 僵尸会话自愈）、`build_frame`（零成本预检）、
`frames`、`simeter()`（wbclient 直连全部方法）、`shell_ro`（只读命令）。

## 3. 判据纪律

- 步骤判定字段是 **`result:"pass"` 字符串**，不是布尔 `pass`；`matched`=对端实际回帧 hex。
- **没带 expect 的 pass 只证明"帧发出去了"**；判"对端有反应"必须带 expect。
- 数值类判据优先"与实际一致"（先读参照量再比对，如 03H-F4 主节点地址 ↔ 10-F104 节点地址），别硬编码用例库里的送检台价值（如厂商码 FC/F8 与台架实值 CF8F 不同）。
- 失败降级要诚实：把根因写进 `supported_reason`（工具链缺口/环境缺位/事件未触发），不写"网络问题"糊弄。

## 4. 硬约束与坑（2026-11-04 全部实测过）

1. **verify 任务 240s 总超时硬闸**：长等待步骤（wait_mclt_stored 900s、expect_timeout>180s）会把 job 拖死强杀；设计原则=单 job ≤240s，长等待拆多轮短窗在用例层循环。
2. **被强杀的任务留僵尸会话占口**：报错 `已被后端会话"模拟集中器"占用` 时，`POST /api/simcon/close` 释放后重试（runner 已内置自愈）。
3. **lease 闸门 no_queue_reject**：并发 409 不硬抢；提交前 `GET /api/ai/v2/simcon/lease`，runner 自动等。
4. **工作台重启会带走 simeter 串口会话**：重开 `POST /api/simeter/open {"mapping_id":"simeter"}`。
5. **F230 存数库只在 simcon 会话开启期间累积**：06H 上报落在无会话窗口即丢；存数类判据必须保证窗口内会话在线。
6. **11E3 自主补抄只在"缺数冻结"后约 9min 发生**：数据齐则不发生；做该事件判据先置 OAD `missing:true` 制造缺数（备份/ finally 恢复）。
7. **STA 模块日志捕获可能停更**（`data/logs/模块/sta/*.log` mtime 验活）：以日志为判据的用例先查 mtime，停更即标 partial（结构性不可达），别空等。
8. **设置类零扰动铁律**：只允许"读原值→写同值→回读"；绝不写不同配置（改地址/超时/时钟/档案都可能毁台架状态）。
9. **1376.2 帧头 13B（68+L2+C1+R6+AFN1+DT2）、尾 CS 1B+16**：手写解析别套 698 的 HCS/FCS 2B 口径。
10. **v1 面要 Bearer token**（`/api/ai/v1/*`），**v2 门面**（`/api/ai/v2/*`）本机 loopback + `WORKBENCH_LOCAL_FULL_ACCESS=1` 免 token，**直连面**（`/api/simcon/*`、`/api/simeter/*`）免 token——本框架统一走 v2。

## 5. 链路与文档

- `chains.json`：`{"<链名>": {"cases": [id…], "stop_on_fail": false, "desc": "..."}}`；建议按"冒烟链 / 端到端链 / 总链"三档。
- runner 每次运行自动写 `results/<ts>_<id>.json` + `results/index.jsonl`，并维护 `docs/<id>.md`，
  标题格式固定三段：**`<测试名> — <支持与否> — <是否已验证运行成功>`**。
- 不可测项也要出文档（静态归类 + 覆盖说明指向可覆盖用例/链路），一次批次通常 300+ 份。

## 6. 红线

- 不 push 任何项目仓库；不重启工作台（除非任务明确要求且按 HANDOVER 环境变量重启）；不改 profile 文件。
- 串口物理独占：simcon 口用例与 cco-main/sta-main 口用例可并行，但同口严格串行。
- 测试项来源以知识库为准，别凭记忆编判据。
