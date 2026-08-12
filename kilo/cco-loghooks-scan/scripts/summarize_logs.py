#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cco-loghooks-scan —— 汇总报告生成
读取 cco_print_scan.json，输出按功能归类的汇总 + 疑问/不确定项。

用法（路径通过环境变量注入，不写死）：
    CCO_OUT=<输出目录> python3 summarize_logs.py
"""
import json
import os
from collections import Counter

OUT_DIR = os.environ.get("CCO_OUT", "")
JSON = os.path.join(OUT_DIR, "cco_print_scan.json")
OUT = os.path.join(OUT_DIR, "cco_print_scan_summary.md")

cat_names = {
    "join": "入网（关联/注册/onnet/黑名单）",
    "collect": "采集上报（MCLT 分钟采集/抄表/数据读取）",
    "send": "发送/上行/转发",
    "beacon": "信标/网络发现/NID/相线",
    "state": "状态机/心跳/周期状态",
    "error": "错误/异常/失败",
    "flash": "烧录/升级/flash 读写",
    "other": "其他",
}


def main():
    if not OUT_DIR:
        raise SystemExit("请通过环境变量指定路径：\n  CCO_OUT=<输出目录> python3 summarize_logs.py")
    recs = json.load(open(JSON, encoding="utf-8"))

    lines = []
    lines.append("# CCO 固件日志打印扫描 —— 汇总报告\n")
    lines.append("> 数据来源：源码扫描（只读采集，未改代码）。")
    lines.append(f"> 清单文件：`cco_print_scan.json`（{len(recs)} 条）与 `cco_print_scan.md`（Markdown 表格）。\n")

    lines.append("## 一、总量概览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 采集打印语句 | {len(recs)} |")
    lines.append(f"| 可正则解析（parsable） | {sum(1 for r in recs if r['parsable'])} |")
    lines.append(f"| 非可解析（仅事件标记） | {sum(1 for r in recs if not r['parsable'])} |")
    lines.append(f"| 高频轮询噪音（periodic） | {sum(1 for r in recs if r['periodic'])} |")
    lines.append(f"| 省份特有（province） | {sum(1 for r in recs if r['scope']=='province')} |")
    lines.append(f"| 通用（common） | {sum(1 for r in recs if r['scope']=='common')} |\n")

    lines.append("## 二、按功能归类汇总\n")
    lines.append("| category | 含义 | 条数 | 通用 | 省份 | 主要文件 |")
    lines.append("|----------|------|------|------|------|----------|")
    cat_count = Counter(r["category"] for r in recs)
    for cat in ["join", "collect", "send", "beacon", "state", "error", "flash", "other"]:
        if cat not in cat_count:
            continue
        sub = [r for r in recs if r["category"] == cat]
        prov = sum(1 for r in sub if r["scope"] == "province")
        common = len(sub) - prov
        files = Counter(r["file"].split("/")[-1] for r in sub)
        top_files = ", ".join(f"{f}({n})" for f, n in files.most_common(4))
        lines.append(f"| {cat} | {cat_names.get(cat,'')} | {len(sub)} | {common} | {prov} | {top_files} |")
    lines.append("")

    lines.append("## 三、省份分布\n")
    lines.append("| 省份 | 条数 | 功能说明 |")
    lines.append("|------|------|----------|")
    prov_count = Counter(r["province"] for r in recs if r["province"])
    for prov, n in sorted(prov_count.items(), key=lambda x: -x[1]):
        sub = [r for r in recs if r["province"] == prov]
        cats = Counter(r["category"] for r in sub)
        desc = ", ".join(f"{cat_names.get(c,c)}:{v}" for c, v in cats.most_common())
        files = Counter(r["file"].split("/")[-1] for r in sub)
        top_files = ", ".join(f for f, _ in files.most_common(3))
        lines.append(f"| `{prov}` | {n} | {desc}（{top_files}） |")
    lines.append("")

    lines.append("## 四、高频轮询噪音行（建议 exclude 或仅作过滤）\n")
    lines.append("> 以下行 `periodic=true`，通常不进规则，或只作 `exclude` 过滤。\n")
    lines.append("| 文件 | 行 | 函数 | 消息 |")
    lines.append("|------|----|------|------|")
    periodic = [r for r in recs if r["periodic"]]
    for r in sorted(periodic, key=lambda x: (x["file"], x["line"]))[:60]:
        lines.append(f"| {r['file'].split('/')[-1]} | {r['line']} | {r.get('func') or ''} | {r['msg'][:50]} |")
    if len(periodic) > 60:
        lines.append(f"| ... | | | 共 {len(periodic)} 条 |")
    lines.append("")

    lines.append("## 五、可作 sequence 状态流的多步骤流程\n")
    lines.append("> 供本侧规划 `sequence` 规则：以下流程在 `context_lines` 中已列出相邻打印。\n")
    from collections import Counter as _C
    flow_files = ["protocol/dll/src/nwk/assoc.c", "protocol/aps/src/aps_register_state.c",
                  "protocol/aps/src/aps_mclt_state.c", "protocol/aps/src/aps_report_state.c",
                  "protocol/aps/src/aps_transdata_state.c", "protocol/aps/src/aps_upgrade_state.c",
                  "protocol/aps/src/aps_stack.c"]
    flow_names = {"protocol/dll/src/nwk/assoc.c": "STA 入网（关联）",
                  "protocol/aps/src/aps_register_state.c": "注册事务",
                  "protocol/aps/src/aps_mclt_state.c": "MCLT 任务配置/采集/轮次",
                  "protocol/aps/src/aps_report_state.c": "上报状态机",
                  "protocol/aps/src/aps_transdata_state.c": "透明传输/上行",
                  "protocol/aps/src/aps_upgrade_state.c": "升级流程",
                  "protocol/aps/src/aps_stack.c": "事件主动上报解析"}
    lines.append("| 流程 | 主要文件 |")
    lines.append("|------|----------|")
    for f in flow_files:
        n = sum(1 for r in recs if r["file"] == f)
        lines.append(f"| {flow_names[f]} | `{f}`（{n} 条） |")
    lines.append("")

    lines.append("## 六、疑问 / 不确定项\n")
    np = sum(1 for r in recs if not r["parsable"])
    nper = sum(1 for r in recs if r["periodic"])
    nunk = sum(1 for r in recs if r["direction"] == "unknown")
    noth = sum(1 for r in recs if r["category"] == "other")
    nhex = sum(1 for r in recs if r["macro"] in ("LOG_HEX", "LOG_HEXDUMP", "LOG2_HEXDUMP", "LOG1_HEXDUMP"))
    lines.append(f"1. **`parsable=false`（{np} 条）**：多为无参数的纯文本标记（如 `p_taffair == NULL!`、`Ts == 0`、`affair over`），仅可作事件标记或跳过，无法转正则 `match`。")
    lines.append("2. **函数归属缺失**：若函数签名跨 100+ 行多行参数（如 `cal_phase_arrange`），自动识别可能遗漏，需人工确认。")
    lines.append("3. **复合省份条件（`||`）**：如 `#if DI_QU_MODE == CHONG_QING_MODE || DI_QU_MODE == HU_NAN_MODE`，记录以 `province=\"chong_qing_mode,hu_nan_mode\"` 标注。规则生成时需注意是『任一省份满足』，不是『两者都满足』。")
    lines.append(f"4. **`direction=unknown`（{nunk} 条）**：多为主机命令处理（`rx_13762_*`）与内部 ioctl，方向语义弱。若需精确可人工补充。")
    lines.append(f"5. **`category=other`（{noth} 条）**：多为调试/测试打印、厂商命令调试、以及无法归类的内部函数。")
    lines.append("6. **`LOG_RAW` 多行拼接**：`assoc.c` 的 `print_bind_topology`/`findBindPcoTeiByLaddr` 用多条 `LOG_RAW` 拼接一行输出（节点 MAC/父 PCO 拓扑树），单条不完整，需整段拼接后解析。")
    lines.append("7. **省份特有**：如 `an_hui_mode` 的 `nwk_intf.c` 绑定周期/BINDING_EN_FLAG 与 `nwk_beacon_para.c` 绑定时隙相线，已标注，不要混入 common。")
    lines.append("8. **省份语义确认**：`hu_nan_mode` 下可能有较多 `rx_13762_*` 主机命令与 `sta_auth_state`（STA 认证）、`_config_scheme_prase`（配置方案解析）等，请确认这些是否为省份特有，还是公共功能被省份宏包裹。")
    lines.append(f"9. **周期判定启发式**：`wait_times`/`Ts`/`trycnt`/`#wait Mut` 等判定为高频（{nper} 条）；`onnet cnt` 标记为 periodic（周期查询入网节点数），但可作 join 状态锚点参考，建议保留但标注高频。")
    lines.append("10. **`raw_format` 含 `__func__`**：部分格式串以 `%s` 开头接 `__func__`，转正则时 `%s` 位置会捕获函数名，需注意。")
    lines.append(f"11. **`LOG_HEX`/`LOG_HEXDUMP`（{nhex} 条）**：为 16 进制数据 dump（MAC/TEI/帧负载），格式是十六进制串，可解析但需按 `raw_format`（如 `buf, len`）展开成连续 hex 正则。")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"summary written: {OUT}")
    print(f"总条数 {len(recs)}，可解析 {sum(1 for r in recs if r['parsable'])}，周期 {nper}，省份 {sum(1 for r in recs if r['scope']=='province')}")


if __name__ == "__main__":
    main()
