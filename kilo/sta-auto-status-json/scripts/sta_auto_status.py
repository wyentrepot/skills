#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sta_auto_status.py — 把 CCO 固件 `sta_upgrade status` 的 [STA-AUTO] 打印解析为 JSON。

输入：标准输入（默认），或参数指定的文件路径（"-" 表示标准输入）。
输出：JSON（UTF-8，中文不转义）。单个状态块时输出扁平对象；多个状态块时输出
      {"blocks": [...]}；无法识别时输出 {"status": "unrecognized", ...}。

用法：
    python3 sta_auto_status.py < sta_auto.log
    python3 sta_auto_status.py sta_auto.log
    echo "[STA-AUTO] ..." | python3 sta_auto_status.py

解析范围：仅状态打印（mode= / firmware= / targets= / boot= / gate: / conditions:
         以及 "status unavailable"）。其它 [STA-AUTO] 行（如 check 输出）会被忽略。
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

PREFIX = "[STA-AUTO] "

MODE_NAMES = {"FORMAL": "正式模式", "TEST": "测试模式"}

STATE_DESC = {
    "DISABLED": "升级功能禁用",
    "WAIT_GATE": "等待升级门限开门",
    "RUNNING": "升级正在执行中",
}

REASON_DESC = {
    "NO_STA_FIRMWARE": "非活跃区固件无效或不存在",
    "TASK_RECORD_ERROR": "任务记录损坏",
    "TASK_COMPLETED": "升级任务已完成",
    "ATTEMPTS_EXHAUSTED": "历史尝试次数已耗尽",
    "BOOT_DELAY": "启动延迟未结束",
    "UPGRADE_RUNNING": "正在执行升级",
    "UPGRADE_AFFAIR_BUSY": "升级事务被占用",
    "CCO_UPGRADING": "CCO 正在升级中",
    "PLATFORM_TEST_MODE": "平台处于测试模式",
    "NO_ATTEMPTS": "本轮无剩余尝试次数",
    "ARCHIVE_EMPTY": "归档设备列表为空",
    "WAIT_ONLINE_95_OR_TIMEOUT": "在线率未达 95% 门限，等待超时强制开门",
    "READY": "一切就绪，允许升级",
    "ROUND_COOLDOWN": "轮次冷却（3 小时）未结束",
    "EXTERNAL_PAUSE": "外部升级后的 6 小时暂停未结束",
    "NO_OWNED_STA": "档案中没有自家 STA",
    "ALL_OWNED_AT_TARGET": "所有自家 STA 均已达到目标版本",
    "UNKNOWN": "未知原因",
}

TASK_STATE_NAMES = {1: "READY", 2: "RUNNING", 3: "COMPLETED", 4: "EXHAUSTED"}
TASK_STATE_DESC = {
    "READY": "就绪，等待执行",
    "RUNNING": "正在执行中",
    "COMPLETED": "已完成，所有目标节点升级成功",
    "EXHAUSTED": "尝试次数耗尽",
}

CONDITION_BLOCK_DESC = {
    "firmware": "非活跃区固件无效",
    "record": "任务记录无效",
    "boot": "启动延迟未结束",
    "affair_idle": "升级事务被占用",
    "cco_idle": "CCO 正在升级",
    "test_allowed": "平台处于测试模式",
    "attempts": "本轮无剩余尝试次数",
    "archive": "归档设备列表为空",
    "ratio_or_timeout": "在线率未达门限且未到强制开门超时",
}

# conditions 打印未覆盖的阻塞原因；此时以 next_reason 为准判定实际阻塞。
REASONS_NOT_COVERED = frozenset({
    "TASK_COMPLETED",
    "ATTEMPTS_EXHAUSTED",
    "ROUND_COOLDOWN",
    "EXTERNAL_PAUSE",
    "NO_OWNED_STA",
    "ALL_OWNED_AT_TARGET",
})


def _int(value: Optional[str]) -> Optional[int]:
    """十进制整数；失败返回 None。"""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _int_hex(value: Optional[str]) -> Optional[int]:
    """十六进制整数（含 0x 前缀）；失败返回 None。"""
    if value is None:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def _int_s(value: Optional[str]) -> Optional[int]:
    """去掉末尾 's' 后转整数，如 '457s' -> 457。"""
    if value is None:
        return None
    return _int(value.rstrip("s"))


def _int_pct(value: Optional[str]) -> Optional[int]:
    """去掉末尾 '%' 后转整数，如 '100%' -> 100。"""
    if value is None:
        return None
    return _int(value.rstrip("%"))


def _normalize_key(key: str) -> str:
    """键名归一化：小写、分隔符统一为下划线、OCR/手输 l<->1 噪声。

    固件键名当前只含字母与下划线（无数字），因此把 '1' 归一为 'l' 是安全的；
    该归一化只作用于键名，绝不作用于值（如 slot=1、task_id=16 保持原值）。
    """
    k = key.strip().lower()
    k = k.replace("-", "_")
    k = k.replace("1", "l")
    return k


def _parse_kv_tokens(text: str) -> Dict[str, str]:
    """把 'k1=v1 k2=v2 k3:v3' 形式的空白分隔 token 解析为字典（键名已归一化）。"""
    out: Dict[str, str] = {}
    for tok in text.split():
        if "=" in tok:
            key, value = tok.split("=", 1)
            out[_normalize_key(key)] = value
        elif ":" in tok:
            key, value = tok.split(":", 1)
            out[_normalize_key(key)] = value
    return out


def parse_status_line(line: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """解析一行状态打印，返回 (行类型, 字段字典)；不是状态行则返回 None。

    兼容两种形态：
    - 带前缀："[STA-AUTO] mode=..."（前缀可出现在行内任意位置，大小写不敏感）；
    - 裸内容："mode=..."（由 _logical_lines 从标签+续行合并而来）。
    """
    m = re.search(r"\[STA-AUTO\]", line, re.IGNORECASE)
    if m:
        rest = line[m.end():].strip()
    else:
        rest = line.strip()
    if rest.startswith("mode="):
        return "mode", _parse_kv_tokens(rest)
    if rest.startswith("firmware="):
        return "firmware", _parse_kv_tokens(rest)
    if rest.startswith("targets="):
        return "targets", _parse_kv_tokens(rest[len("targets="):])
    if rest.startswith("boot="):
        return "boot", _parse_kv_tokens(rest)
    if rest.startswith("gate:"):
        return "gate", _parse_kv_tokens(rest[len("gate:"):])
    if rest.startswith("conditions:"):
        return "conditions", _parse_kv_tokens(rest[len("conditions:"):])
    if rest.lower() == "status unavailable":
        return "unavailable", {}
    return None


_TRUE_VALUES = frozenset({"ok", "yes", "true", "done", "valid", "busy", "y", "1"})
_FALSE_VALUES = frozenset({"no", "false", "wait", "idle", "invalid", "none", "n", "0"})


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    """大小写不敏感地解析状态值：ok/yes/done/valid/busy -> True；
    no/wait/idle/invalid/none -> False；其它返回 None。"""
    if value is None:
        return None
    v = value.strip().lower()
    if v in _TRUE_VALUES:
        return True
    if v in _FALSE_VALUES:
        return False
    return None


def _canon(value: Optional[str]) -> Optional[str]:
    """把自由文本值归一到大写规范形式（用于 mode/state/next_reason）。"""
    if value is None:
        return None
    return value.strip().upper()


def build_conclusion(b: Dict[str, Any]) -> str:
    parts: List[str] = []
    state = b.get("state")
    if state:
        parts.append("状态 %s（%s）" % (state, b.get("state_desc") or state))

    if b.get("conditions") is not None:
        blocking = list(b.get("blocking") or [])
        extra = list(b.get("blocking_extra") or [])
        if not blocking and not extra:
            parts.append("所有条件满足，允许升级")
        else:
            descs = [CONDITION_BLOCK_DESC.get(k, k) for k in blocking]
            for r in extra:
                desc = REASON_DESC.get(r, r)
                if r == "ROUND_COOLDOWN" and b.get("round_cooldown_seconds") is not None:
                    desc = ("轮次冷却（3 小时）未结束（剩余 %ds）"
                            % b["round_cooldown_seconds"])
                elif r == "EXTERNAL_PAUSE" and b.get("external_pause_seconds") is not None:
                    desc = ("外部升级后的 6 小时暂停未结束（剩余 %ds）"
                            % b["external_pause_seconds"])
                elif r == "ALL_OWNED_AT_TARGET" and b.get("need_upgrade_count") == 0:
                    desc = "所有自家 STA 均已达到目标版本（need_upgrade=0）"
                descs.append(desc)
            if "boot" in blocking and b.get("boot_delay_remaining_seconds") is not None:
                descs[blocking.index("boot")] = (
                    "启动延迟未结束（剩余 %ds）"
                    % b["boot_delay_remaining_seconds"]
                )
            parts.append("阻塞条件：" + "；".join(descs))
            passed = sum(1 for v in b["conditions"].values() if v is True)
            total = len(b["conditions"])
            parts.append("%d/%d 条件满足" % (passed, total))
    else:
        reason = b.get("next_reason")
        if reason:
            parts.append("原因：" + (REASON_DESC.get(reason, reason) or reason))

    if b.get("task_id") is not None and b.get("need_upgrade_count") is not None:
        tip = "待升级自家 STA %d 台" % b["need_upgrade_count"]
        tip += "（任务 %d" % b["task_id"]
        if b.get("storage_slot") is not None:
            tip += "，目标 slot %d" % b["storage_slot"]
        if b.get("attempts_remaining") is not None:
            tip += "，剩余尝试 %d 次" % b["attempts_remaining"]
        tip += "）"
        parts.append(tip)

    return "，".join(parts)


def build_block(kind_fields: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    b: Dict[str, Any] = {}
    mode_f = kind_fields.get("mode", {})
    fw_f = kind_fields.get("firmware", {})
    tgt_f = kind_fields.get("targets", {})
    boot_f = kind_fields.get("boot", {})
    gate_f = kind_fields.get("gate", {})
    cond_f = kind_fields.get("conditions", {})

    # --- 模式 / 状态 / 原因 ---
    b["mode"] = _canon(mode_f.get("mode"))
    b["mode_name"] = MODE_NAMES.get(b["mode"], b["mode"])
    b["attempt_mode"] = _int(mode_f.get("attempt_mode"))
    b["max_attempts"] = _int(mode_f.get("max_attempts"))
    state = _canon(mode_f.get("state"))
    b["state"] = state
    b["state_desc"] = STATE_DESC.get(state or "", state)
    reason = _canon(mode_f.get("next"))
    b["next_reason"] = reason
    b["next_reason_desc"] = REASON_DESC.get(reason or "", reason)

    # --- 固件 / 任务 ---
    b["firmware_valid"] = _parse_bool(fw_f.get("firmware"))
    b["firmware_status"] = fw_f.get("firmware")
    b["task_record_valid"] = _parse_bool(fw_f.get("record"))
    b["task_record_status"] = fw_f.get("record")
    b["task_id"] = _int(fw_f.get("task_id"))
    b["storage_slot"] = _int(fw_f.get("slot"))
    b["storage_offset"] = _int_hex(fw_f.get("offset"))
    b["storage_offset_hex"] = fw_f.get("offset")
    b["image_size"] = _int(fw_f.get("size"))
    b["image_crc32"] = fw_f.get("crc")
    b["attempts_remaining"] = _int(fw_f.get("attempts"))
    lifecycle = _int(fw_f.get("lifecycle"))
    b["task_state_code"] = lifecycle
    task_state = TASK_STATE_NAMES.get(lifecycle) if lifecycle is not None else None
    b["task_state"] = task_state
    b["task_state_desc"] = TASK_STATE_DESC.get(task_state or "", task_state)

    # --- 目标 / 冷却 ---
    b["owned_count"] = _int(tgt_f.get("owned"))
    b["need_upgrade_count"] = _int(tgt_f.get("need_upgrade"))
    b["round_cooldown_seconds"] = _int_s(tgt_f.get("round_cooldown"))
    b["external_pause_seconds"] = _int_s(tgt_f.get("external_pause"))

    # --- 启动延迟 / 轮询 / 事务 ---
    b["boot_delay_done"] = _parse_bool(boot_f.get("boot"))
    b["boot_delay_status"] = boot_f.get("boot")
    b["boot_delay_remaining_seconds"] = _int_s(boot_f.get("remaining"))
    b["poll_seconds"] = _int_s(boot_f.get("poll"))
    b["affair_busy"] = _parse_bool(boot_f.get("affair"))
    b["affair_status"] = boot_f.get("affair")
    b["cco_upgrading"] = _parse_bool(boot_f.get("cco_upgrade"))
    b["platform_test_mode"] = _parse_bool(boot_f.get("platform_test"))

    # --- 门限 ---
    b["gate_online_count"] = _int(gate_f.get("online"))
    b["gate_archive_count"] = _int(gate_f.get("archive"))
    b["gate_online_percent"] = _int_pct(gate_f.get("ratio"))
    b["gate_required_percent"] = _int_pct(gate_f.get("required"))
    waited_s = gate_f.get("waited", "")
    if waited_s and "/" in waited_s:
        w_part, m_part = waited_s.split("/", 1)
        b["gate_waited_seconds"] = _int_s(w_part)
        b["gate_max_wait_seconds"] = _int_s(m_part)
    else:
        b["gate_waited_seconds"] = _int_s(waited_s) if waited_s else None
        b["gate_max_wait_seconds"] = None
    b["gate_ready"] = (
        _parse_bool(cond_f.get("ratio_or_timeout")) or _gate_ready_from_numbers(b)
    )

    # --- 条件 ---
    conditions: Dict[str, bool] = {}
    if cond_f:
        for k, v in cond_f.items():
            conditions[k] = _parse_bool(v)
        b["conditions"] = conditions
        b["conditions_all_ok"] = (
            all(v is True for v in conditions.values()) if conditions else None
        )
        b["blocking"] = [k for k, v in conditions.items() if v is False]
    else:
        b["conditions"] = None
        b["conditions_all_ok"] = None
        b["blocking"] = []

    # conditions 打印未覆盖的阻塞原因（冷却/暂停/无目标等），以 next_reason 为准。
    blocking_extra: List[str] = []
    if (b.get("conditions") is not None) and (not b["blocking"]):
        reason = b.get("next_reason")
        if reason in REASONS_NOT_COVERED:
            blocking_extra = [reason]
    b["blocking_extra"] = blocking_extra

    b["conclusion"] = build_conclusion(b)
    return b


def _gate_ready_from_numbers(b: Dict[str, Any]) -> Optional[bool]:
    """门限行缺失时，用数值推断：有归档且（在线率达标或等待超时）。"""
    if b.get("gate_archive_count") is None:
        return None
    if b.get("gate_archive_count") == 0:
        return False
    if b.get("gate_online_percent") is None or b.get("gate_required_percent") is None:
        return None
    if b["gate_online_percent"] >= b["gate_required_percent"]:
        return True
    if (
        b.get("gate_waited_seconds") is not None
        and b.get("gate_max_wait_seconds") is not None
        and b["gate_waited_seconds"] >= b["gate_max_wait_seconds"]
    ):
        return True
    return False


def _logical_lines(text: str) -> List[str]:
    """把 '[STA-AUTO]' 标签与后续缩进续行合并为逻辑行（标签大小写不敏感）。

    兼容终端换行粘贴的两种形态：
    - 标签与内容同行："[STA-AUTO] mode=..."；
    - 标签独占一行、内容在下一行缩进（终端自动换行/复制粘贴常见）。
    非缩进、非标签的行（如 shell 提示符）会中止当前逻辑行，不会被吞并。
    """
    logical: List[str] = []
    current: Optional[str] = None
    for raw in text.splitlines():
        m = re.search(r"\[STA-AUTO\]", raw, re.IGNORECASE)
        if m:
            if current is not None:
                logical.append(current)
            current = raw[m.end():].strip()
            continue
        if current is not None:
            if raw.startswith((" ", "\t")):
                current += " " + raw.strip()
            else:
                logical.append(current)
                current = None
    if current is not None:
        logical.append(current)
    return logical


def parse_text(text: str) -> Dict[str, Any]:
    blocks: List[Dict[str, Any]] = []
    kind_fields: Dict[str, Dict[str, str]] = {}
    onnet_counts: List[int] = []
    dev_counts: List[int] = []

    for raw in text.splitlines():
        line = raw.strip()
        m = re.search(r"onnet\s+cnt\s*=\s*(\d+)", line, re.IGNORECASE)
        if m:
            try:
                onnet_counts.append(int(m.group(1)))
            except ValueError:
                pass
        m = re.search(r"devCntToNwk\s+(\d+)", line, re.IGNORECASE)
        if m:
            try:
                dev_counts.append(int(m.group(1)))
            except ValueError:
                pass

    for logical in _logical_lines(text):
        parsed = parse_status_line(logical)
        if parsed is None:
            continue
        kind, fields = parsed
        if kind == "mode" and kind_fields:
            blocks.append(build_block(kind_fields))
            kind_fields = {}
        if kind == "unavailable":
            blocks.append({"status": "unavailable"})
            kind_fields = {}
            continue
        kind_fields[kind] = fields

    if kind_fields:
        blocks.append(build_block(kind_fields))

    result: Dict[str, Any] = {"matched_blocks": len(blocks)}
    context: Dict[str, Any] = {}
    if onnet_counts:
        context["net_onnet_count"] = onnet_counts[-1]
    if dev_counts:
        context["net_dev_count"] = dev_counts[-1]
    if context:
        result["context"] = context
    if not blocks:
        result["status"] = "unrecognized"
        return result
    if len(blocks) == 1:
        result.update(blocks[0])
        return result
    result["blocks"] = blocks
    return result


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        print("usage: sta_auto_status.py [FILE|-]", file=sys.stderr)
        return 2
    if args and args[0] != "-":
        try:
            with open(args[0], "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            print("sta_auto_status.py: cannot read %s: %s" % (args[0], exc),
                  file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()

    result = parse_text(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
