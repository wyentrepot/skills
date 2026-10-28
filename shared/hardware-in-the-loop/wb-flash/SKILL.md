---
name: wb-flash
description: 什么时候用我：要把 iap 固件烧进 STA/CCO 并判定「真烧成了」——提交 flash job、拿 job_id、看懂「Bootloader prompt was not detected」、弄清烧录 403「未配置允许烧录目录」、curl 超时后不确定是否还在烧、烧完回读开机横幅核对 isv/sver/hver。只做烧录：模拟电表去 wb-simeter，串口会话与桥 preflight 去 wb-serial，离线帧解析去 wb-appframe，授权签发与总门面去 ai-control-plane。
argument-hint: "[端 sta|cco] [件绝对路径]"
metadata:
  author: reasonix
  version: 1.0.0
  applies-to: 本机工作台 8790（<WORKBENCH_ROOT> 见 ai-control-plane「路径根解析」）
  source: 拆自 ai-control-plane（2026-10-28）
---

# 烧录子技能（wb-flash）

**本技能只讲一件事：用工作台 HTTP 面把 `iap_*.bin` 烧进 STA/CCO，并用会话日志判定成功。**
别的事不归我：模拟电表/对档联调 → `wb-simeter`；串口会话、串口桥 preflight 细节、观察取证 → `wb-serial`；离线帧解析/构帧 → `wb-appframe`；侦听台查帧 → `wb-listener`；授权签发与 v2 任务门面 → `ai-control-plane`（只读总入口）。下文只留烧录必需的最小判据，别处不重复。

## 1. 前置三查（缺一项就别提交）

### 查 1 · 授权必须带 `firmware_roots`
```bash
# 授权归人：AI 不自签、不扩权；仅限 workbench 本机 127.0.0.1 + admin key
curl -X POST http://127.0.0.1:8790/api/ai/v1/admin/grants \
  -H "X-Workbench-Admin-Key: <WORKBENCH_AI_ADMIN_KEY>" -H "Content-Type: application/json" \
  -d '{"scopes":["module_session:ensure","module_flash:execute","evidence:read"],"resources":["*"],
       "firmware_roots":["/home/H_STA/01/sta/build/artifacts"],"ttl_seconds":3600,"reason":"烧录 sta 件"}'
```

- `firmware_roots` = 允许烧录的目录白名单；缺它 → 403「当前授权未配置允许烧录目录」（Bearer/局域网面；`local_full` 例外见下条）。**403 不是缺陷**，正确解是签发时带目录；禁止重启工作台塞 env 绕过（等于自扩权）。本机 loopback + `WORKBENCH_LOCAL_FULL_ACCESS=1` 时 v2 免 token，局域网必须 `Bearer <token>`（token 只返回一次，别写进日志/提交）。
- **已知安全缺口（2026-10-28 实测，如实记在这里）**：v2 `local_full` 下 `firmware_roots` 白名单**根本不校验**——零授权、无 `firmware_roots` 也把 STA 烧成了。这是**缺口，不是推荐用法**（白名单只在 Bearer/局域网面生效，P1-2 会收紧）。**团队红线：烧录必须由人授权**，不许因为"能绕过"就这么干，也不许据此跳过查 1。

> 来源：references/auth.md:6-21、references/module-serial.md:65、交接-20261028.md:66
> 来源：validation-20261028/F5（T4 实机：未签发授权、无 `firmware_roots`，v2 `local_full` 未返 403 即烧成）

### 查 2 · 串口桥 status + verify
```bash
curl -s http://127.0.0.1:8790/api/serial-bridge/status | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8790/api/serial-bridge/verify \
  -H 'Content-Type: application/json' -d '{"ports":["sta-main"],"open":true}'
```

- **过线按目标口判**：目标口 `workbench_ready=true` 且（`checks.open_ok=true` **或** `checks.in_use=true`）。`ok` 只是全局汇总，**别的口离线不阻塞本口**；**`ok=false` 只在目标口自身 `ports[].errors` 非空时才算阻塞**，再按 errors 报层级（WSL 桥 / Windows 双通道 / 软链 / 映射 `parity` 必须 N）。
- 口被已有会话占住时是 `checks.open_ok=null` + `in_use=true`（`ok` 仍可为 `true`）：`in_use=true` 只说明该口此刻无法自证可打开，**不阻塞烧录**。标签与物理口可能对不上，**别硬编码 COM 号**，一律用 `mapping_id`。

> 来源：references/serial-bridge.md:7-20,40-52；references/module-serial.md:3-6；交接-20261028.md:25
> 来源：validation-20261028/F1（T4 实机：`sta-main` 被占 → `ok=true`+`workbench_ready=true`+`in_use=true`+`open_ok=null`）

### 查 3 · 只认 `iap_*.bin`
| 件名 | 是什么 | 能走串口 IAP 吗 |
| --- | --- | --- |
| `iap_{cco,sta}_*.bin` | IAP 升级镜像，几百 KB | ✅ **只烧这个** |
| `flash_*.bin` | 生产整片镜像，~2 MB | ❌ bootloader 不认，实测 ~24%（~503 KB）后停止 ACK 并中止 |
| `upgrade_*.dat` | 另一条串口升级格式 | ❌ 与 bootloader XMODEM 无关 |

不确定先读 `firmware/readme.txt`（文件1=生产 flash / 文件2=iap 串口升级 / 文件3=upgrade）。

> 来源：references/module-serial.md:51-57；references/_归档-门面v2.9.md:144-145；交接-20261028.md:83-84

## 2. 提交烧录

先拿 `session_id`（`ms-xxxx`）：v2 `module-actions`(action=ensure) 或 v1 `module-sessions/ensure` `{"module":"sta","mapping_id":"sta-main"}`；409=串口占用（物理独占，非 bug）。然后：

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v2/flash-jobs -H "Content-Type: application/json" \
  -d '{"session_id":"ms-xxxx","bin_path":"<firmware_roots 内>/iap_sta_..._isv060088_idate261027.bin",
       "slot":0,"client_request_id":"flash-sta-20261028-01"}' \
  --max-time 300 -o 02-flash-create.json
```

- 必填 `session_id`、`bin_path`（绝对路径，**必须落在 `firmware_roots` 内**）；可省 `slot`(0)/`baud_plan`(115200)/`no_reboot_after`(false)。
- **受理是异步的（2026-10-28 修复并实测）**：`POST flash-jobs` **0.13 s 就返回** `202 + JobEnvelope(job_state=running)`，真实烧录在后台跑。`--max-time 300` 仍建议留着，但**不必再怕超时**。
  - 旧版是同步阻塞（要等 121 s 才回、客户端先超时），这个坑已在 `1a7e6db` 修掉；若你碰到某台机器仍要等满烧录时长，说明它跑的是旧代码。
- `verdict` 对 flash 恒 `null`——烧录成功**不**伪装成 `pass`；`job_state` 走向 `running → succeeded|error`。
- **job_id 怎么拿**：就是响应体里的 `job_id`，建议 `-o` 落盘；**丢了不用再翻 json 文件**——`GET /api/ai/v2/jobs?kind=flash_job&limit=10` 直接列最近的烧录任务摘要（含派生 `job_id`），拿到 id 再 `GET /api/ai/v2/jobs/{job_id}`。
  - 兜底：`<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json`（不在 `data/` 下）。

> 来源：references/api-contract.md:246-265；apps/workbench/ai_contracts.py:158-165,187-198；apps/workbench/ai_v2_api.py:299-322

## 3. 进 bootloader 的正确姿势（2026-10-28 08:40 实测）
```
发 reboot\r\n      → 0.59 s 出现 "Unicorn Bootloader" + "Press 'd' key to enter bootloader mode!"
每 50 ms 发一个 d  → 0.70 s 出现 "You can input command 'help' or '?'"   ⇒ 已在 bootloader
```

- **不需要精确窗口**：`reboot` 后持续狂发 `d` 就能稳定撞进；"必须卡 12 秒窗口"的旧说法作废。
- 工装本来就这么做，正常烧录**不用手搓**：`_invoke_bootloader_navigation()` 见 `Press 'd' key` 自动发 `d`；`_test_bootloader_text()` 只认 `[image /]#` 或 `You can input command`（拿 banner 里 `enter bootloader mode` 当判据会误判）。
- 手搓脚本只用于"这口到底能不能进 bootloader"的现场自证；**跑前先 stop 会话**（串口独占）。

```python
#!/usr/bin/env python3   # 自证 sta-main 能进 bootloader；会独占 PTY，先 stop 会话
import time, serial
ser = serial.Serial("/run/hplc/serial/sta-main", 115200, timeout=0, parity=serial.PARITY_N)  # pts 不吃 PARENB
buf = b""
def pump(sec, send_d=False):
    deadline = time.time() + sec
    while time.time() < deadline:
        if send_d: ser.write(b"d")          # 50 ms 一发，不对齐窗口
        chunk = ser.read(4096); buf += chunk
        time.sleep(0.05)
ser.reset_input_buffer(); ser.write(b"reboot\r\n"); pump(0.5)   # 0.59 s 后应出 Unicorn Bootloader
pump(3.0, send_d=True)                              # 狂发 d：0.70 s 量级进 bootloader
text = bytes(buf).decode("ascii", "replace"); print(text[-2000:])
print("BOOTLOADER OK" if ("You can input command" in text or "[image /]#" in text) else "NOT IN BOOTLOADER")
ser.close()
```

> 来源：交接-20261028.md:70-78；evidence/build/sta-console-probe-20261027.md:44-56；apps/module_log/xmodem_flash.py:195-251,379-420

## 4. 三个坑（必须醒目）
### ✅ 坑 1（已修 2026-10-28，纪律仍守）· 重提 flash job 曾会二次烧录
```
ai_capability_service.py:341  payload.pop("client_request_id")   ← 幂等键交给内层前被删，内层收不到
ai_capability_service.py:353  if parent["state"] != "created": return  ← 父 job 整个烧录期还是 created，判断不成立 → 再烧一遍
module_serial_service.py:389  if self._flash_state["flashing"]: raise   ← 只盖住正在烧那段，烧完即放行
```

- 实测事故：CCO 21:44:06 起烧 → 21:46:42 `BURN SUCCESS`；因 curl 超时用**同一 `client_request_id`** 重提 → 又起一次 → 21:46:58 `烧录失败：Bootloader prompt was not detected.`（设备已在跑新件，未覆盖成功镜像）。
- **已修（`1a7e6db`，2026-10-28 实机验证）**：父 job 开烧前即落 `waiting`、幂等键以 `<key>:module_flash` 透传内层、受理段加进程内锁。实测同键重提 **0.033 s 返回同一个 `job_id`、只产生 1 个 `module_flash`**；同会话换新键并发提交 → **409「该会话已有烧录任务在执行，烧录不可并发」**。
- **纪律不变**：拿结果永远用 `GET /api/ai/v2/jobs/{job_id}`（`wait_seconds≤30`，轮询快照无副作用），不要靠重提去"催"。运营边界：重启会把旧的非终态 flash_job 标 `interrupted` 且其幂等键仍被占用，这时同键重提会拿到那个 interrupted job（不会重烧），**要重烧请换新键**。

### ✅ 坑 2（已修 2026-10-28）· 曾因同步阻塞导致 curl 超时假失败

- **旧版**：handler 内 `control.flash_module()` 是同步调用，响应要等整段烧录跑完才回（实测 121 s，STA 08:35:14→08:37:15），`curl -m 60` 必然先超时、响应体 0 字节——**那时设备很可能已经在烧**。
- **现已异步（`1a7e6db`）**：受理 0.13 s 返回 job_id。但**若你仍遇到超时**（例如连的是旧版服务），照旧处置：**看会话日志，别当失败、别重提、别断电**。
- 处置：`--max-time 300` 或不设超时；已经超时了 → **看会话日志**，别当失败、别重提、别断电。

### ⚠️ 坑 3 · 不可取消、不可并发重试

- `POST /jobs/{id}/cancel` 对 flash 显式拒绝：「烧录或模拟集中器验证任务不可取消」（`ai_capability_service.py:373`）；烧录中再提交撞 flashing 互斥：「烧录已在执行中」（`module_serial_service.py:390`）→ 409，不是故障。
- 唯一正确姿势：**等**——`GET /jobs/{job_id}?wait_seconds=30` + 会话日志事件，直到终态。

> 来源：REQS.md:105,109-122；apps/workbench/ai_capability_service.py:341-373；apps/module_log/module_serial_service.py:389-390；evidence/run/flash-cco-20261027-2144/README.md:24-28；evidence/run/flash-sta-20261028/README.md:22-27

## 5. 判定表（BURN SUCCESS 怎么认）
| # | 判据 | 合格值（实测样例） |
| --- | --- | --- |
| 1 | 会话日志事件行 | `[EVENT] 烧录完成：BURN SUCCESS`（工装写的，最硬） |
| 2 | 包数与字节数 | `packet=478/478 bytes=489288/489288`（CCO）、`368/368`+`375900/375900`（STA），pct=100，**全等** |
| 3 | 收尾握手 | `XMODEM EOT ACK` + `Image download OK!` |
| 4 | 烧后横幅 | STA `isv:060088 / sver:002732 / hver:0101 / isv date:2026-10-27`；CCO `fc sversion : 090028` |
| 5 | 件名**部分**比对 | 横幅实出 **6 行**（`boot_ver` / `sdk_ver` / `hver` / `sver` / `isv` / `isv date`），件名 `hv0101_sv002732_isv060088_idate261027` 只有 **4 项可比**：`hv0101→hver`、`sv002732→sver`、`isv060088→isv`、`idate261027→isv date`；**`date261027` 与 `FC_F8` 在横幅里没有对应字段，不可比**（CCO 另证 `isv 090017→090028`，21:46:47 与 21:58:57 两次独立采样） |

- **横幅从哪来**：`no_reboot_after=false`（默认）时**烧完自动重启**，六行横幅就在**会话日志的 `[RX]` 行**里（实测 11:43:58 烧完、11:44:00 出横幅），**不需要再手工 reboot 一次**；`03H-F1` 只读到 **CCO** 版本，**读不到 STA**（协议级 STA 版本回读另案）。`job_state=succeeded` 只代表跑完：**烧成没成看判据 1~3，烧的是不是这个件看判据 4~5 的那 4 项**，两边都要过。
- **失败了先看哪里**：`job_state=failed`（或 `error`）时 L1/L2 可能**全是 `items:[]`**、只有 `summary:"flash_job error"`；真因在该 op 的 `error` 字段里，文件是 **`<WORKBENCH_ROOT>/apps/workbench/runtime/ai-control/operations.json`**（**不在** `<WORKBENCH_ROOT>/data/...` 下），op id 取信封的 `underlying_refs` / `result.underlying_operation_id`。**证据全空不等于"没原因"**，不要据此断定无法归因。

> 来源：evidence/run/flash-cco-20261027-2144/README.md:7-16；evidence/run/flash-sta-20261028/README.md:5,17,29-43,51-53；apps/module_log/module_serial_service.py:424
> 来源：validation-20261028/F4（failed job 证据 `items:[]`）、F7（T4 `banner_block.txt` 六行横幅；`date261027`/`FC_F8` 无对应字段）
## 6. 证据清单（缺了就写清为什么缺）
| # | 要落的 | 怎么落 |
| --- | --- | --- |
| 1 | 件：路径 + 字节数 + md5 | 烧前当场 `md5sum`（CCO `7b85…bc4a`/489288 B、STA `3401…c86`/375900 B） |
| 2 | job 请求体 + 响应信封 | `01-request.json` / `02-flash-create.json`（`curl -o`）；异步化后 0.13 s 就该拿到 `job_id`，**没拿到要写明原因**（连的是不是旧版服务 / 网络问题） |
| 3 | 会话日志原件 | `data/logs/模块/<模块>/<时间戳>_<mapping>.log` 整份留档（含毫秒时间戳） |
| 4 | 烧后横幅 + 事件摘录 + 一行结论 | 从会话日志取烧后自动重启的六行横幅原文（**不必再手工 reboot**）；摘 开始烧录 / progress / EOT ACK / BURN SUCCESS；结论写 端·件·md5·slot·session·包数·job_state·判定 |

**红线**：不重提 flash job；烧录中途不断电、不抢串口；不用 `flash_*.bin` 顶 `iap_*.bin`；烧完 stop 释放串口。

> 来源：evidence/run/flash-sta-20261028/README.md:13-27；evidence/run/flash-cco-20261027-2144/README.md:3-16；交接-20261028.md:29-36,67
## 附录 · 深水事实库（答不清才翻，别整份读）

- `references/operation-guide.md`（519 行）§5 烧录固件原始步骤；`references/api-contract.md`（490 行）§6 flash-jobs 字段级契约；`references/module-serial.md`（68 行）会话与烧录接口；`references/_归档-门面v2.9.md`（257 行，**仅当新文档查不到时**）。
- 铁律：事实库改动只改一处；子技能**不复制**事实库内容，避免两份说法打架。
