---
name: sta-auto-status-json
description: Use when the user pastes [STA-AUTO] status prints from the CCO firmware `sta_upgrade status` command (lines like mode=FORMAL ..., firmware=VALID ..., targets= ..., boot= ..., gate: ..., conditions: ...) or asks 这个打印什么状态 / STA 自主升级状态 / 这个日志什么状态. Run the bundled parser script and reply with its JSON result plus a short conclusion — never hand-parse these logs.
metadata:
  author: cco
  version: "1.1.0"
  applies-to: /home/H_CCO/001/cco
---

# sta-auto-status-json（STA 自主升级状态打印解析）

## 概述

CCO 固件 `sta_upgrade status`（或 `sta_upgrade`）会打印 6 行 `[STA-AUTO]` 状态（mode / firmware / targets / boot / gate / conditions）。
本技能用自带脚本把这些打印解析成 JSON，并直接回复结论。**不要手工逐行解读日志，一律运行脚本。**

## 何时使用

- 用户贴出包含 `[STA-AUTO]` 的状态打印（`mode=`/`firmware=`/`targets=`/`boot=`/`gate:`/`conditions:`）。
- 用户问“这个打印什么状态”“这个日志什么状态”“STA 自主升级状态”。
- 不适用于 `sta_upgrade check` 等其它 `[STA-AUTO]` 输出（脚本会静默忽略），也不适用于普通网络日志。

## 步骤

1. 把用户贴的日志原样喂给脚本（脚本自动忽略时间戳、`onnet cnt` 等无关行；支持文件参数或 stdin）：

```bash
SKILL_DIR=/home/02-skill-fc/skills/kilo/sta-auto-status-json
python3 "$SKILL_DIR/scripts/sta_auto_status.py" <<'EOF'
<用户粘贴的日志>
EOF
# 或：python3 "$SKILL_DIR/scripts/sta_auto_status.py" < log.txt
```

2. 直接把脚本输出的 JSON 贴给用户（代码块），并附脚本生成的 `conclusion` 一句话结论。
3. `blocking` 或 `blocking_extra` 非空时补充说明阻塞原因与预期下一步（例如“启动延迟剩余 457s，结束后开始升级 1 台 STA”“轮次冷却剩余 10680s，冷却结束前不发起本轮”）；`status=unrecognized` 时说明未识别到状态打印；多条日志一起贴会按 `mode=` 分行成多个块（输出 `{"blocks": [...]}`）。

## JSON 字段速查

| 字段 | 含义 |
|---|---|
| `state` / `next_reason` | 状态机状态（WAIT_GATE/RUNNING/DISABLED）/ 当前阻塞原因（READY=允许升级） |
| `firmware_valid` / `task_record_valid` | 非活跃区固件 / 任务记录有效性 |
| `task_id` / `storage_slot` / `storage_offset(_hex)` / `image_size` / `image_crc32` / `attempts_remaining` / `task_state` | 升级任务信息（lifecycle 已映射为 READY/RUNNING/COMPLETED/EXHAUSTED） |
| `owned_count` / `need_upgrade_count` / `round_cooldown_seconds` / `external_pause_seconds` | 目标与冷却统计 |
| `boot_delay_done` / `boot_delay_remaining_seconds` / `poll_seconds` / `affair_busy` / `cco_upgrading` / `platform_test_mode` | 启动延迟与占用情况 |
| `gate_online_count` / `gate_archive_count` / `gate_online_percent` / `gate_required_percent` / `gate_waited_seconds` / `gate_max_wait_seconds` / `gate_ready` | 在线率门限 |
| `conditions` / `conditions_all_ok` / `blocking` | 9 项条件布尔值与未满足项列表 |
| `blocking_extra` | 条件打印未覆盖的阻塞原因（轮次冷却/外部暂停/无目标/任务已完成/次数耗尽等），以 `next_reason` 为准 |
| `conclusion` | 一句话中文结论（可直接引用回复用户） |

## 常见错误

- 手工解读而不是运行脚本 → 直接运行脚本拿 JSON。
- 只贴部分行 → 脚本支持缺行，缺失字段为 `null`，照常输出。
- 粘贴被破坏（`[STA-AUTO]` 标签与内容被拆成两行、大小写混乱、`_`变`-`、`l`↔`1`、`ok/No` 小写）→ 脚本已兼容：标签+缩进续行自动合并、键名与值大小写不敏感，照常解析。
- 中文乱码 → 脚本已 `ensure_ascii=False`，原样展示即可。

## 回归测试

`test/sample.log` + `test/sample.expected.json` 为样例：

```bash
SKILL_DIR=/home/02-skill-fc/skills/kilo/sta-auto-status-json
python3 "$SKILL_DIR/scripts/sta_auto_status.py" "$SKILL_DIR/test/sample.log" > /tmp/sta-auto-out.json
diff "$SKILL_DIR/test/sample.expected.json" /tmp/sta-auto-out.json && echo PASS
```
