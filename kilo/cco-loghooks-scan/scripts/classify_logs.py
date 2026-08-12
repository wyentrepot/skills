#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cco-loghooks-scan —— 语义分类层
读取 cco_print_scan.raw.json，为每条记录标注：
  category / direction / periodic / trigger / anchor / context_lines / parsable
产出最终 cco_print_scan.json 与 cco_print_scan.md

用法（路径通过环境变量注入，不写死）：
    CCO_SRC=<源码根目录> CCO_OUT=<输出目录> python3 classify_logs.py
"""
import json
import os
import re

SRC_ROOT = os.environ.get("CCO_SRC", "")
OUT_DIR = os.environ.get("CCO_OUT", "")

RAW = os.path.join(OUT_DIR, "cco_print_scan.raw.json")
OUT_JSON = os.path.join(OUT_DIR, "cco_print_scan.json")
OUT_MD = os.path.join(OUT_DIR, "cco_print_scan.md")

JOIN_MARKERS = ["assoc", "join", "reg", "onnet", "入网", "assocreq", "assocCnf", "AssocNack",
                "AssocGather", "blacklist", "blackList", "offnet", "off_net", "UNASSOC", "ONNET",
                "rejoin", "re_join", "join_src", "laddr_seq", "IdChanged", "sta_join"]

COLLECT_MARKERS = ["mclt", "clt", "collect", "meter", "抄表", "冻结", "fz_time", "round", "snapshot",
                   "task_id", "data_read", "DATA_READ", "11e3", "11e4", "11e2", "smeter", "tmeter",
                   "mid_cnt", "freeze", "minute", "rpt_mclt", "mcltlist", "meteraddr", "cfg_scheme"]

SEND_MARKERS = ["send", "tx", "trans", "submit", "push", "to_nwk", "rpt", "up", "上送", "上行",
                "send_to_nwk", "send_len", "to localcom", "to_localcom", "uplink", "rptSend"]

BEACON_MARKERS = ["bcn", "beacon", "nid", "信标", "srr", "tei", "phase", "NTB", "ntb", "ZeroCross",
                  "zc_", "phase_line", "csma", "slot", "coord"]

STATE_MARKERS = ["state", "heartbeat", "心跳", "period", "timer", "wait_times", "retry", "timeout",
                 "Ts == 0", "trycnt", "bpsCheck", "tick", "poll", "init", "affair"]

ERROR_MARKERS = ["err", "fail", "NULL", "null", "无", "失败", "错误", "invalid", "overflow", "not in list",
                 "not find", "crash", "reset"]

FLASH_MARKERS = ["flash", "erase", "wr ", "write", "upgrade", "升级", "烧录", "exflash", "ver_cfg",
                 "isv", "firmware", "file_upgrade", "version"]


def classify_category(msg, func, file):
    m = (msg + " " + (func or "") + " " + file).lower()
    if any(k in m for k in ["err", "fail", "overflow", "not find", "null", "invalid"]) and \
       not any(k in m for k in ["onnet", "assoc", "mclt", "bcn", "beacon"]):
        return "error"
    if any(k in m for k in JOIN_MARKERS):
        return "join"
    if any(k in m for k in COLLECT_MARKERS):
        return "collect"
    if any(k in m for k in SEND_MARKERS):
        return "send"
    if any(k in m for k in BEACON_MARKERS):
        return "beacon"
    if any(k in m for k in STATE_MARKERS):
        return "state"
    if any(k in m for k in FLASH_MARKERS):
        return "flash"
    if any(k in m for k in ERROR_MARKERS):
        return "error"
    return "other"


def classify_direction(msg, func, macro):
    m = (msg + " " + (func or "")).lower()
    if any(k in m for k in ["rx", "recv", "receive", "ind", "indicate", "on_", "getrx", "prase",
                            "in_", "read", "ack deal", "deal", "_rx_", "rx_", "in"]):
        return "RX"
    if any(k in m for k in ["tx", "send", "trans", "submit", "push", "to_nwk", "rpt", "up",
                            "send_len", "assocreq send", "assocCnf", "AssocNackSend", "rptSend",
                            "localcom", "to_local", "out"]):
        return "TX"
    if any(k in m for k in ["state", "timer", "timeout", "retry", "period", "tick", "heartbeat",
                            "init", "affair", "check", "deal", "set", "get", "prase", "parse",
                            "struct", "list", "pool", "config", "cfg", "flash", "erase", "create",
                            "delete", "remove", "add", "clear", "upgrade", "status", "printf",
                            "print", "test", "save", "update", "alloc", "flush", "ioctl", "poll",
                            "change", "select", "choice", "fill", "reg"]):
        return "EVENT"
    return "unknown"


# 高频轮询/周期行（periodic=true）——通常不进规则，或只作过滤
PERIODIC_PATTERNS = [
    r"trycnt",
    r"bpsCheck_state0",
    r"#wait Mut",
    r"nwkLockEnter",
    r"select rp :",
    r"record_diff",
    r"get_order_phase",
    r"select_cco_ntb",
    r"cco_ntb - sta_ntb",
    r"sta_ntb - cco_ntb",
    r"pahse %d csma %d",
    r"blackList length == 0",
    r"laddPollInit",
    r"wait_times",
    r"heartbeat",
    r"cmsa period end",
    r"csma_hplc_task_enter",
    r"p_affair->Ts:%d",   # 状态机等待倒计时
]


def classify_periodic(msg, func):
    m = msg + " " + (func or "")
    for p in PERIODIC_PATTERNS:
        if re.search(p, m, re.I):
            return True
    return False


def classify_parsable(msg, params):
    m = msg
    # 有真正的 printf 转换符（%d/%x/%s/%u 等）→ 可解析
    if re.search(r"%\d*(?:\.\d+)?[dxXuulfcsp]", m, re.I):
        return True
    # 有标签化的值（key=value 或 key: value）
    if re.search(r"\b(?:tei|nid|addr|laddr|mac|cnt|count|task(?:_id)?|ssn|phase|seq|sn|num|total|idx|index|ret|err|res|len|datalen)[:=]", m, re.I):
        return True
    # 有实参（可被 capture）
    if params:
        return True
    return False


# 锚点：可作为跨来源关联的业务标识
def classify_anchor(msg, params, func):
    m = msg.lower()
    anchors = []
    for p in params:
        pn = p.get("name", "")
        pl = pn.lower()
        if "tei" in pl or "nid" in pl or "mac" in pl or "laddr" in pl or "addr" in pl:
            anchors.append({"param": pn, "type": "ADDR"})
        if "task" in pl and ("id" in pl or "ssn" in pl):
            anchors.append({"param": pn, "type": "TASK"})
        if "ssn" in pl:
            anchors.append({"param": pn, "type": "SSN"})
        if "phase" in pl:
            anchors.append({"param": pn, "type": "PHASE"})
        if "seq" in pl or "sn" in pl:
            anchors.append({"param": pn, "type": "SEQ"})
    if not anchors and re.search(r"tei[:\.]? ?%", msg):
        anchors.append({"param": None, "type": "TEI"})
    if not anchors and re.search(r"nid", m):
        anchors.append({"param": None, "type": "NID"})
    return anchors if anchors else None


# 权威业务流标注：(file, func) -> (category, direction, trigger, periodic, anchor_type)
# 命中则优先，否则用关键字兜底。这是人工经验沉淀，可按项目扩展。
AUTHORITATIVE = {
    # --- 入网流程 (STA 入网：发现→关联→跟踪→收信标) ---
    ("protocol/dll/src/nwk/assoc.c", "assocreq"): ("join", "RX", "收到 STA 关联请求", False, None),
    ("protocol/dll/src/nwk/assoc.c", "assocCnf_send"): ("join", "TX", "发送关联确认", False, None),
    ("protocol/dll/src/nwk/assoc.c", "AssocNackSend"): ("join", "TX", "发送关联拒绝", False, None),
    ("protocol/dll/src/nwk/assoc.c", "AssocGatherSend"): ("join", "TX", "转发关联汇聚报文", False, None),
    ("protocol/dll/src/nwk/assoc.c", "AssocGantherSendCheck"): ("join", "EVENT", "关联汇聚发送检查", True, None),
    ("protocol/dll/src/nwk/assoc.c", "AssocGantherRfSendCheck"): ("join", "EVENT", "RF 关联汇聚发送检查", True, None),
    ("protocol/dll/src/nwk/assoc.c", "save_assoc_info"): ("join", "EVENT", "保存关联信息（节点入网落库）", False, "TEI"),
    ("protocol/dll/src/nwk/assoc.c", "choice_pco"): ("join", "EVENT", "PCO 选择", False, "TEI"),
    ("protocol/dll/src/nwk/assoc.c", "fill_dsdt_list"): ("join", "EVENT", "填充下行设备表", False, "TEI"),
    ("protocol/dll/src/nwk/assoc.c", "fill_route_info"): ("join", "EVENT", "填充路由信息", False, None),
    ("protocol/dll/src/nwk/assoc.c", "cco_update_sta_route"): ("join", "EVENT", "更新 STA 路由", False, "TEI"),
    ("protocol/dll/src/nwk/assoc.c", "getBindPcoTei"): ("beacon", "EVENT", "查询绑定 PCO TEI", False, "TEI"),
    ("protocol/dll/src/nwk/assoc.c", "findBindPcoTeiByLaddr"): ("beacon", "EVENT", "按长地址查绑定 PCO", False, "MAC"),
    ("protocol/dll/src/nwk/assoc.c", "print_bind_topology"): ("other", "EVENT", "打印绑定拓扑（调试）", False, "SNID"),

    # --- STA 地址池 / 离网 ---
    ("protocol/dll/src/nwk/sta.c", "laddPollInitPowerOn"): ("join", "EVENT", "上电地址池初始化", False, None),
    ("protocol/dll/src/nwk/sta.c", "laddPollInit"): ("join", "EVENT", "地址池初始化", False, None),
    ("protocol/dll/src/nwk/sta.c", "laddPollInit2"): ("join", "EVENT", "地址池初始化2", False, None),
    ("protocol/dll/src/nwk/sta.c", "teiGetByMacAddr"): ("join", "EVENT", "按 MAC 获取 TEI", False, "MAC"),
    ("protocol/dll/src/nwk/sta.c", "macAddrDel"): ("join", "EVENT", "删除 MAC（离网/换表）", False, "MAC"),
    ("protocol/dll/src/nwk/sta.c", "IsBlackList"): ("join", "EVENT", "黑名单检查", False, "MAC"),
    ("protocol/dll/src/nwk/sta.c", "BlackListAdd"): ("join", "EVENT", "加入黑名单", False, "MAC"),
    ("protocol/dll/src/nwk/sta.c", "BlackListTimeFlush"): ("join", "EVENT", "黑名单时效刷新", True, "MAC"),
    ("protocol/dll/src/nwk/sta.c", "DelayLeavelCheck"): ("join", "EVENT", "延迟离网检查", False, "TEI"),
    ("protocol/dll/src/nwk/sta.c", "MMeLeaveIndSend"): ("join", "TX", "发送离网指示", False, None),
    ("protocol/dll/src/nwk/sta.c", "StaIsMySubNode"): ("state", "EVENT", "子节点关系检查", False, "TEI"),
    ("protocol/dll/src/nwk/sta.c", "change_sta_level"): ("state", "EVENT", "节点层级变更", False, "TEI"),
    ("protocol/dll/src/nwk/sta.c", "save_phase"): ("beacon", "EVENT", "保存相线", False, "PHASE"),

    # --- 信标 / 网络发现 ---
    ("protocol/dll/src/nwk/nwk_bcn.c", "creat_bcn_beg"): ("beacon", "TX", "开始组帧信标", False, None),
    ("protocol/dll/src/nwk/nwk_bcn.c", "creat_bcn_end"): ("beacon", "TX", "结束组帧信标", False, None),
    ("protocol/dll/src/mac/mac_recv_task.c", "Bcn crc"): ("beacon", "RX", "收到信标 CRC 校验", False, "NID"),

    # --- APS 上报（抄表/主动上报） ---
    ("protocol/aps/src/aps_report_state.c", "rptSend"): ("send", "TX", "上报发送", False, None),
    ("protocol/aps/src/aps_report_state.c", "_tx_report_to_localcom"): ("send", "TX", "上报到本地口", False, None),
    ("protocol/aps/src/aps_report_state.c", "report_state0"): ("state", "EVENT", "上报状态机0", False, None),
    ("protocol/aps/src/aps_report_state.c", "report_state1"): ("state", "EVENT", "上报状态机1", False, None),
    ("protocol/aps/src/aps_report_state.c", "report_state2"): ("state", "EVENT", "上报状态机2", False, None),
    ("protocol/aps/src/aps_report_state.c", "report_state3"): ("state", "EVENT", "上报状态机3", False, None),
    ("protocol/aps/src/aps_report_state.c", "pwr_evt_check"): ("state", "EVENT", "停电事件检查", False, "TEI"),

    # --- MCLT 分钟采集 ---
    ("protocol/aps/src/aps_mclt_state.c", "mclt_affair_init"): ("collect", "EVENT", "MCLT 事务初始化", False, None),
    ("protocol/aps/src/aps_mclt_state.c", "send_to_nwk"): ("collect", "TX", "MCLT 下发到网络层", False, "TASK"),
    ("protocol/aps/src/aps_mclt_state.c", "nwk_mclt_data_ack_deal"): ("collect", "RX", "MCLT 数据 ACK 处理", False, "TASK"),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_struct_cfg"): ("collect", "EVENT", "MCLT 任务配置解析", False, "TASK"),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_struct_clean_cfg"): ("collect", "EVENT", "MCLT 清除配置", False, "TASK"),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_struct_clt"): ("collect", "TX", "MCLT 采集下发", False, "TASK"),
    ("protocol/aps/src/aps_mclt_state.c", "rpt_mclt_idle"): ("collect", "TX", "MCLT 空闲上报", False, "TASK"),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_round_finish"): ("collect", "EVENT", "MCLT 轮次结束", False, "TASK"),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_state0"): ("state", "EVENT", "MCLT 状态机0", False, None),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_state1"): ("state", "EVENT", "MCLT 状态机1", False, None),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_state3"): ("state", "EVENT", "MCLT 状态机3", False, None),
    ("protocol/aps/src/aps_mclt_state.c", "mclt_state4"): ("state", "EVENT", "MCLT 状态机4", False, None),
    ("protocol/aps/src/mclt_list.c", "get_config_scheme_len"): ("collect", "EVENT", "获取配置方案长度", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "get_config_scheme"): ("collect", "EVENT", "获取配置方案", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "copy_config_scheme"): ("collect", "EVENT", "复制配置方案", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mcltlist_new"): ("collect", "EVENT", "新建 MCLT 任务链表", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mcltlist_delete"): ("collect", "EVENT", "删除 MCLT 任务", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mclt_task_reactivate_cfg"): ("collect", "EVENT", "MCLT 任务重新激活配置", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "minute_meter_init"): ("collect", "EVENT", "分钟表初始化", False, None),
    ("protocol/aps/src/mclt_list.c", "mclt_meter_clting_total"): ("collect", "EVENT", "统计采集中的表", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mclt_meter_cfging_total"): ("collect", "EVENT", "统计配置中的表", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mclt_meter_running_total"): ("collect", "EVENT", "统计运行中的表", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mclt_task_status"): ("collect", "EVENT", "任务状态查询", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "rd_task_status"): ("collect", "EVENT", "读任务状态", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "set_meter_cfg_by_addr"): ("collect", "EVENT", "按地址设置表配置", False, "MAC"),
    ("protocol/aps/src/mclt_list.c", "set_meter_clt_by_addr"): ("collect", "EVENT", "按地址设置表采集", False, "MAC"),
    ("protocol/aps/src/mclt_list.c", "clear_meter_addr_by_taskid"): ("collect", "EVENT", "按任务清表地址", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mclt_meterAddr_clt_clear"): ("collect", "EVENT", "清表采集标志", False, "TASK"),
    ("protocol/aps/src/mclt_list.c", "mclt_meterAddr_clt_clear_by_taskid"): ("collect", "EVENT", "按任务清表采集标志", False, "TASK"),
    ("protocol/aps/src/mclt_snapshot.c", "mclt_snapshot_move_task_for_delete"): ("collect", "EVENT", "快照任务搬家删除", False, "TASK"),
    ("protocol/aps/src/mclt_snapshot.c", "mclt_snapshot_force_remove_task"): ("collect", "EVENT", "强制移除快照任务", False, "TASK"),
    ("protocol/aps/src/mclt_snapshot.c", "mclt_snapshot_force_remove_all_tasks"): ("collect", "EVENT", "强制清空快照任务", False, "TASK"),

    # --- 上行转发 / 数据读取 ---
    ("protocol/aps/src/aps_transdata_state.c", "transdata_affair_init"): ("send", "EVENT", "透明传输事务初始化", False, None),
    ("protocol/aps/src/aps_transdata_state.c", "transdata_state_init"): ("state", "EVENT", "透明传输状态机初始化", False, None),
    ("protocol/aps/src/aps_intf.c", "_event_report_prase"): ("send", "RX", "事件主动上报解析", False, "MAC"),
    ("protocol/aps/src/aps_intf.c", "ONNET"): ("join", "EVENT", "节点入网状态变更", False, "MAC"),
    ("protocol/aps/src/aps_intf.c", "UNASSOC"): ("join", "EVENT", "节点失联", False, "MAC"),

    # --- 状态机/心跳 ---
    ("protocol/aps/src/aps_register_state.c", "register_affair_init"): ("join", "EVENT", "注册事务初始化", False, None),
    ("protocol/aps/src/aps_register_state.c", "register_state_init"): ("state", "EVENT", "注册状态机初始化", False, None),
    ("protocol/aps/src/aps_register_state.c", "rpt_register_finish"): ("join", "TX", "上报注册完成", False, None),
    ("protocol/aps/src/aps_ioctrl_nwk.c", "aps_to_nwk_onnet_node_num_get"): ("join", "EVENT", "查询入网节点数", True, None),
}


def main():
    if not SRC_ROOT or not OUT_DIR:
        raise SystemExit(
            "请通过环境变量指定路径：\n"
            "  CCO_SRC=<源码根目录> CCO_OUT=<输出目录> python3 classify_logs.py"
        )
    with open(RAW, encoding="utf-8") as f:
        recs = json.load(f)

    from collections import defaultdict
    lines_by_func = defaultdict(list)
    for r in recs:
        lines_by_func[(r["file"], r.get("func") or "")].append(r["line"])

    for r in recs:
        key = (r["file"], r.get("func") or "")
        auth = AUTHORITATIVE.get(key)
        if auth:
            cat, dr, trig, peri, anch = auth
            r["category"] = cat
            r["direction"] = dr
            r["trigger"] = trig
            r["periodic"] = peri
            if anch:
                r["anchor"] = {"type": anch}
            else:
                r["anchor"] = classify_anchor(r["msg"], r.get("params", []), r.get("func"))
        else:
            r["category"] = classify_category(r["msg"], r.get("func"), r["file"])
            r["direction"] = classify_direction(r["msg"], r.get("func"), r["macro"])
            r["periodic"] = classify_periodic(r["msg"], r.get("func"))
            r["trigger"] = ""
            r["anchor"] = classify_anchor(r["msg"], r.get("params", []), r.get("func"))

        r["parsable"] = classify_parsable(r["msg"], r.get("params", []))

        # 语义化参数（清理三元表达式/强制转换/尾括号等）
        clean_params = []
        for p in r.get("params", []):
            name = p["name"].strip()
            while name.endswith(")"):
                name = name[:-1]
            if "?" in name and ":" in name:
                name = name.split("?")[1].split(":")[0].strip()
            if not name or name in ('NULL', 'null'):
                continue
            name = re.sub(r"^\([^)]*\)\s*", "", name)
            name = re.sub(r"^&\s*", "", name)
            if not name:
                continue
            sem = name
            if re.search(r"tei", name, re.I):
                sem = name + " → 网络地址TEI"
            elif re.search(r"(laddr|mac|addr)", name, re.I):
                sem = name + " → 长地址/MAC"
            elif re.search(r"nid", name, re.I):
                sem = name + " → 网络标识NID"
            elif re.search(r"task", name, re.I):
                sem = name + " → 采集任务ID"
            elif re.search(r"ssn", name, re.I):
                sem = name + " → 序号SSN"
            elif re.search(r"(cnt|count|total|num)", name, re.I):
                sem = name + " → 计数/数量"
            elif re.search(r"err|res", name, re.I):
                sem = name + " → 错误码/返回值"
            elif re.search(r"phase", name, re.I):
                sem = name + " → 相线"
            clean_params.append({"name": name, "semantic": sem})
        r["params"] = clean_params

        ctx = [ln for ln in lines_by_func[key] if ln != r["line"]]
        r["context_lines"] = sorted(ctx)[:12]

        if not r.get("trigger"):
            r["trigger"] = trigger_from_msg(r["msg"], r.get("func"), r["category"], r["macro"])

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=2)
    print(f"JSON written: {OUT_JSON} ({len(recs)} records)")

    header = ["file", "line", "func", "macro", "msg", "params", "parsable", "direction",
              "trigger", "periodic", "category", "scope", "province", "anchor", "context_lines"]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# CCO 固件日志打印扫描清单\n\n")
        f.write("> 数据来源：源码诚实采集；本文件与 `cco_print_scan.json` 同源。\n\n")
        f.write("| " + " | ".join(header) + " |\n")
        f.write("|" + "|".join(["---"] * len(header)) + "|\n")
        for r in recs:
            params_s = ";".join(f"{p['name']}({p['semantic']})" for p in r.get("params", []))
            ctx_s = ",".join(map(str, r.get("context_lines", [])))
            anchor_s = r.get("anchor") if r.get("anchor") else ""
            if isinstance(anchor_s, (dict, list)):
                anchor_s = json.dumps(anchor_s, ensure_ascii=False)
            row = [
                r["file"].split("/")[-1], str(r["line"]), r.get("func") or "", r["macro"],
                (r["msg"] or "").replace("|", "\\|").replace("\n", " ")[:60],
                params_s.replace("|", "\\|")[:60],
                str(r["parsable"]), r["direction"], (r.get("trigger") or "").replace("|", "\\|")[:40],
                "Y" if r["periodic"] else "N", r["category"], r["scope"], r.get("province") or "",
                anchor_s, ctx_s[:40],
            ]
            f.write("| " + " | ".join(row) + " |\n")
    print(f"MD written: {OUT_MD}")


def trigger_from_msg(msg, func, cat, macro):
    if macro in ("LOG_ERR", "LOG2_ERR", "LOG1_ERR"):
        return "错误/异常触发"
    if macro in ("LOG_WARN", "LOG2_WARN", "LOG1_WARN"):
        return "告警/异常条件触发"
    if cat == "error":
        return "异常/失败路径"
    if cat == "collect":
        return "采集/任务处理"
    if cat == "join":
        return "入网/关联流程"
    if cat == "send":
        return "发送/上行流程"
    if cat == "beacon":
        return "信标/网络维护"
    if cat == "flash":
        return "烧录/升级流程"
    if cat == "state":
        return "状态机/周期处理"
    return "业务处理"


if __name__ == "__main__":
    main()
