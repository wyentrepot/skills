#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cco-loghooks-scan —— 机械提取层
扫描 CCO 固件源码中的日志打印语句（LOG* 宏 / LOG_PRINTF / printf 家族），
输出结构化清单原始产物。

只做诚实采集，不改任何代码。

用法（路径通过环境变量注入，不写死）：
    CCO_SRC=<源码根目录> CCO_OUT=<输出目录> python3 extract_logs.py
环境变量默认值见 main()。
"""
import os
import re
import json

SRC_ROOT = os.environ.get("CCO_SRC", "")
OUT_DIR = os.environ.get("CCO_OUT", "")

# 扫描目录：业务相关 .c 文件（排除 SDK/libdepend/unity 等非业务与测试）
SCAN_DIRS = [
    "protocol/aps/src",
    "protocol/dll/src/nwk",
    "protocol/dll/src/mac",
    "protocol/phy/src",
    "app",
    "components/src",
    "dev",
    "misc",
    "misc/src",
    "bsp/src",
]

EXCLUDE_DIRS = {
    "bsp/venus/sdk",       # vendor SDK
    "test",                # test code, not firmware
}

# 日志宏（按参数个数区分，便于解析）
MACRO_1ARG = ["LOG_INFO", "LOG_ERR", "LOG_WARN", "LOG_OK", "LOG_FAIL", "LOG_DBG",
              "LOG2_INFO", "LOG2_ERR", "LOG2_WARN", "LOG2_OK", "LOG2_FAIL", "LOG2_DBG",
              "LOG1_INFO", "LOG1_ERR", "LOG1_WARN", "LOG1_OK", "LOG1_FAIL", "LOG1_DBG",
              "LOG_RAW", "LOG1_RAW", "LOG2_RAW"]
MACRO_HEX = ["LOG_HEX", "LOG_HEXDUMP", "LOG2_HEXDUMP", "LOG1_HEXDUMP"]
MACRO_ADDR = ["LOG_IP6ADDR", "LOG_LONGADDR", "LOG1_IP6ADDR", "LOG1_LONGADDR", "LOG2_IP6ADDR", "LOG2_LONGADDR"]

MACRO_RE = re.compile(
    r"\b(?:LOG2?_(?:INFO|ERR|WARN|OK|FAIL|DBG|RAW|HEX|HEXDUMP|IP6ADDR|LONGADDR|PRINTF))\b"
)


def build_func_index(lines):
    """构造 行号->函数名 索引：按花括号配对，行 i 属于哪个函数"""
    FUNC_RE = re.compile(
        r"^(?:(?:static|inline|const|unsigned|signed|volatile|register)\s+)?"
        r"(?:[A-Za-z_]\w*\s+)*"  # 任意类型前缀（含 INT8U/INT16U/s_xxx_t/e_xxx_t 等）
        r"([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{?\s*$"
    )
    func_of_line = {}
    cur_func = None
    depth = 0
    prev_sig = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip()
        code = line.split("//")[0].rstrip()
        m = FUNC_RE.match(code)
        sig = None
        if m and m.group(1) not in ("if", "for", "while", "switch", "return", "else", "do"):
            sig = m.group(1)
        ends_brace = code.endswith("{")
        if sig is not None:
            if ends_brace:
                cur_func = sig
                depth = code.count("{") - code.count("}")
                func_of_line[i] = cur_func
                if depth <= 0:
                    cur_func = None
                prev_sig = None
            else:
                prev_sig = (i, sig)
        elif prev_sig is not None and code.strip() == "{":
            cur_func = prev_sig[1]
            depth = 1
            func_of_line[i] = cur_func
            prev_sig = None
        elif ends_brace and prev_sig is None and cur_func is None and "(" in code:
            nm = re.search(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{?\s*$", code)
            if nm and nm.group(1) not in ("if", "for", "while", "switch"):
                cur_func = nm.group(1)
                depth = 1
                func_of_line[i] = cur_func
        if cur_func is not None and not ends_brace and sig is None:
            func_of_line[i] = cur_func
        if sig is not None and ends_brace:
            pass
        elif cur_func is not None and sig is None and not (prev_sig is not None and code.strip() == "{"):
            opened = code.count("{")
            closed = code.count("}")
            depth += opened - closed
            if depth <= 0:
                cur_func = None
        elif prev_sig is not None and code.strip() == "{":
            pass
        i += 1
    return func_of_line


def find_function_fallback(lines, idx):
    """回溯找函数名：适配多行签名"""
    ctrl = {"if", "for", "while", "switch", "return", "else", "do"}
    for i in range(idx - 1, max(-1, idx - 120), -1):
        line = lines[i]
        code = line.split("//")[0]
        if "(" not in code or code.rstrip().endswith(";"):
            continue
        nm = re.search(r"([A-Za-z_]\w*)\s*\(", code)
        if not nm or nm.group(1) in ctrl:
            continue
        for j in range(i, min(idx + 1, i + 8)):
            if "{" in lines[j].split("//")[0]:
                return nm.group(1)
        if "{" in code:
            return nm.group(1)
    return None


def parse_call(lines, line_idx, pos, macro):
    """从 lines[line_idx][pos:] 开始解析宏调用，跨多行。返回 (args_text, end_line_idx) 或 (None, None)"""
    buf = []
    depth = 0
    in_str = False
    i = pos
    li = line_idx
    line = lines[li]
    started = False
    first_open = True
    while li < len(lines):
        if li != line_idx:
            line = lines[li]
        j = i if li == line_idx else 0
        while j < len(line):
            c = line[j]
            if in_str:
                buf.append(c)
                if c == "\\":
                    if j + 1 < len(line):
                        buf.append(line[j + 1])
                        j += 2
                        continue
                elif c == '"':
                    in_str = False
                j += 1
                continue
            if c == '"':
                in_str = True
                started = True
                buf.append(c)
                j += 1
                continue
            if c == "(":
                if first_open:
                    first_open = False
                else:
                    depth += 1
                started = True
                buf.append(c)
                j += 1
                continue
            if c == ")":
                if depth == 0:
                    buf.append(c)
                    return "".join(buf)[1:], li
                depth -= 1
                buf.append(c)
                j += 1
                continue
            if c == "/" and j + 1 < len(line) and line[j + 1] == "/":
                break
            if started:
                buf.append(c)
            j += 1
        li += 1
        if li < len(lines):
            started = True
            buf.append(" ")
    return None, None


def strip_comment(line):
    """去掉行内 // 注释和 /* */ 注释（粗略）"""
    out = []
    i = 0
    n = len(line)
    in_str = False
    while i < n:
        c = line[i]
        if in_str:
            out.append(c)
            if c == "\\":
                i += 1
                if i < n:
                    out.append(line[i])
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            break
        if c == "/" and i + 1 < n and line[i + 1] == "*":
            i += 2
            while i + 1 < n and not (line[i] == "*" and line[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def extract_format_arg(args_text):
    """从参数文本中提取第一个字符串字面量（格式串）"""
    args_text = args_text.rstrip().rstrip(")")
    m = re.search(r'"((?:[^"\\]|\\.)*)"', args_text)
    if not m:
        return None
    return m.group(0), m.group(1)


def extract_params(args_text, fmt):
    """提取格式串之后的实参（变量名/表达式）"""
    args_text = args_text.rstrip().rstrip(")")
    m = re.search(r'"((?:[^"\\]|\\.)*)"', args_text)
    if not m:
        return []
    rest = args_text[m.end():].strip()
    if not rest:
        return []
    params = []
    depth = 0
    cur = ""
    for c in rest:
        if c == "(":
            depth += 1
            cur += c
        elif c == ")":
            depth -= 1
            cur += c
        elif c == "," and depth == 0:
            params.append(cur.strip())
            cur = ""
        else:
            cur += c
    if cur.strip():
        params.append(cur.strip())
    cleaned = []
    for p in params:
        p = re.sub(r"^\([^)]*\)\s*", "", p)
        p = re.sub(r"^&\s*", "", p)
        p = re.sub(r"^\(void\s*\*\)\s*", "", p)
        cleaned.append(p)
    return [c for c in cleaned if c]


def get_enum_direction(expr):
    """依据表达式关键词粗判 RX/TX/EVENT"""
    e = expr.lower()
    if re.search(r"\b(rx|recv|receive|ind|indicate|in_|on_|read)\b", e):
        return "RX"
    if re.search(r"\b(tx|send|transmit|submit|push|out_|write|to_nwk|to_dl)\b", e):
        return "TX"
    if re.search(r"\b(state|timer|evt|event|timeout|tick|period|task)\b", e):
        return "EVENT"
    return "unknown"


def prov_of_cond(cond):
    """返回省份集合 set。识别 DI_QU_MODE == XXX 及 || 组合"""
    provs = set()
    for m in re.finditer(r"DI_QU_MODE\s*==\s*(\w+)", cond):
        p = m.group(1).lower()
        if p != "common_mode":
            provs.add(p)
    return provs


def main():
    if not SRC_ROOT or not OUT_DIR:
        raise SystemExit(
            "请通过环境变量指定路径：\n"
            "  CCO_SRC=<源码根目录> CCO_OUT=<输出目录> python3 extract_logs.py"
        )
    records = []
    files = []
    for d in SCAN_DIRS:
        full = os.path.join(SRC_ROOT, d)
        if not os.path.isdir(full):
            continue
        for root, dirs, fnames in os.walk(full):
            dirs[:] = [x for x in dirs if os.path.join(root, x) not in EXCLUDE_DIRS]
            for fn in sorted(fnames):
                if fn.endswith(".c"):
                    files.append(os.path.join(root, fn))

    for fp in sorted(files):
        rel = os.path.relpath(fp, SRC_ROOT)
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")
        func_idx = build_func_index(lines)

        # 预解析省份上下文：记录每个 DI_QU_MODE #if 行激活的省份集合
        prov_at_line = {}
        pre_stack = []
        active_provs = set()
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("#if "):
                cond = s[4:]
                provs = prov_of_cond(cond)
                pre_stack.append({"provs": provs, "active": bool(provs and not active_provs)})
                if provs and not active_provs:
                    active_provs = provs
            elif s.startswith("#elif"):
                if pre_stack:
                    e = pre_stack[-1]
                    provs = prov_of_cond(s[5:])
                    e["provs"] = provs
                    if active_provs == e.get("prev_provs"):
                        active_provs = set()
                    e["active"] = bool(provs and not active_provs)
                    if provs and not active_provs:
                        active_provs = provs
                    e["prev_provs"] = provs
            elif s.startswith("#else"):
                if pre_stack:
                    e = pre_stack[-1]
                    e["active"] = not active_provs
            elif s.startswith("#endif"):
                if pre_stack:
                    e = pre_stack.pop()
                    if active_provs == e.get("provs", set()) or (e.get("active") and active_provs == e.get("provs", set())):
                        active_provs = set()
            prov_at_line[i] = (active_provs.copy() if active_provs else None)

        clean_lines = [strip_comment(l) for l in lines]
        for i, line in enumerate(lines):
            if "LOG_" not in line:
                continue
            clean = clean_lines[i]
            s = clean.strip()
            if s.startswith("#define") and "(" in s.split("LOG")[0] if "LOG" in s else False:
                continue
            if s.startswith("#") and "define" in s:
                continue
            for m in MACRO_RE.finditer(clean):
                macro = m.group(0)
                args_text, _ = parse_call(clean_lines, i, m.start(), macro)
                if args_text is None:
                    continue
                _fa = extract_format_arg(args_text)
                fmt, raw_fmt = _fa if _fa else (None, None)
                provs = prov_at_line.get(i)
                prov = (",".join(sorted(provs)) if provs else None)
                if fmt is None:
                    records.append({
                        "file": rel, "line": i + 1,
                        "func": func_idx.get(i) or find_function_fallback(lines, i),
                        "macro": macro, "raw_format": args_text[:80], "msg": args_text[:80],
                        "params": [], "parsable": False, "direction": "unknown",
                        "trigger": "", "periodic": False, "category": "other",
                        "scope": "province" if prov else "common",
                        "province": prov,
                        "anchor": None, "context_lines": [],
                        "uncertain": "no format string literal",
                    })
                    continue
                params = extract_params(args_text, fmt)
                records.append({
                    "file": rel, "line": i + 1,
                    "func": func_idx.get(i) or find_function_fallback(lines, i),
                    "macro": macro, "raw_format": raw_fmt, "msg": fmt,
                    "params": [{"name": p, "semantic": p} for p in params],
                    "parsable": None,
                    "direction": get_enum_direction(fmt + " " + " ".join(params)),
                    "trigger": "", "periodic": False, "category": "other",
                    "scope": "province" if prov else "common",
                    "province": prov,
                    "anchor": None, "context_lines": [],
                    "uncertain": "",
                })

    print(f"extracted {len(records)} log statements from {len(files)} files")
    os.makedirs(OUT_DIR, exist_ok=True)
    raw_path = os.path.join(OUT_DIR, "cco_print_scan.raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print("raw written to", raw_path)


if __name__ == "__main__":
    main()
