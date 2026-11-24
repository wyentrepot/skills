#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wb — 工作台执行层 CLI（wb-base 自带，烧录链第一批）。

把 SKILL.md 里的判据固化进代码，AI 只跑命令 + 判读输出，不再手搓 curl：

  wb health                       8790 探活
  wb status                       8766 宿主控制面 + 8790 + 串口桥 一屏
  wb preflight <mapping_id>       开串口前过线判定（判据：usable / workbench_ready，
                                  in_use 不算失败；不用全局 ok 判单口）
  wb auth --scopes ...            签最小权限 grant（需要 WORKBENCH_AI_ADMIN_KEY）
  wb session ensure <cco|sta>     确保模块串口会话，打印 session_id
  wb flash submit <iap_*.bin>     提交烧录 job（幂等键默认 md5 派生，防二次烧录）
  wb wait <job_id>                等终态；失败时自动按 ①steps.reason ②sent_hex
                                  ③L1 证据 ④operations.json 顺序归因
  wb evidence <job_id> [--level]  读证据

红线已由代码保证：不重提 flash job（幂等键默认确定性）、wait 是唯一取结果入口、
不硬编码 COM 号（一律 mapping_id）、token 不进输出（--json 除外，仍遮蔽 token 字段）。

退出码：0 成功；1 判定不过/任务失败；2 用法错误；3 连不上/环境缺配置。

契约原文与兜底 curl 序列：wb-base/SKILL.md（§1–§7）；本脚本只是执行层，契约以文档为准。
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

BASE = os.environ.get("WORKBENCH_BASE", "http://127.0.0.1:8790")
ADMIN_KEY = os.environ.get("WORKBENCH_AI_ADMIN_KEY", "")
AI_TOKEN = os.environ.get("WORKBENCH_AI_TOKEN", "")

TERMINAL = ("succeeded", "failed", "error", "stopped", "cancelled", "interrupted")
FLASH_HOSTS = ("cco", "sta")


class WbError(Exception):
    def __init__(self, code, message, exit_code=1):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


# ---------------------------------------------------------------- HTTP

def _token():
    return AI_TOKEN or ""


def req(method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    tok = _token()
    if tok:
        headers["Authorization"] = "Bearer " + tok
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"detail": str(e)}
        payload.setdefault("http_error", e.code)
        return payload
    except Exception as e:
        raise WbError("conn", "工作台不在线（%s 连接失败：%s）。启动见 wb-base §1.2。" % (BASE, e), 3)


def get(path, timeout=60):
    return req("GET", path, timeout=timeout)


def post(path, body=None, timeout=60):
    return req("POST", path, body, timeout)


def out(ctx, text):
    ctx["lines"].append(text)


def flush(ctx):
    text = "\n".join(ctx["lines"])
    if ctx.get("json"):
        return text
    print(text)
    return None


def mask(obj):
    """--json 输出前遮蔽 token 字段（token 只返回一次、不进日志/提交）。"""
    if isinstance(obj, dict):
        return {k: ("***" if "token" in k.lower() and isinstance(v, str) else mask(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask(x) for x in obj]
    return obj


# ---------------------------------------------------------------- WORKBENCH_ROOT（wb-base §1.1 同序）

def workbench_root():
    env = os.environ.get("WORKBENCH_ROOT")
    if env and os.path.isdir(env):
        return env
    cfg = os.path.expanduser("~/.config/workbench/repo-root")
    if os.path.isfile(cfg):
        p = open(cfg).read().strip()
        if p and os.path.isdir(p):
            return p
    d = os.getcwd()
    for cand in (d, os.path.join(d, ".."), os.path.join(d, "../.."),
                 os.path.join(d, "../../..")):
        if os.path.isdir(os.path.join(cand, "apps", "workbench")):
            return cand
    return None


# ---------------------------------------------------------------- 8766 宿主控制面（wb-base §1.4）

def host_8766():
    host = None
    try:
        route = subprocess.run(["ip", "route", "show", "default"], capture_output=True,
                               text=True, timeout=5).stdout
        host = route.split()[2] if len(route.split()) > 2 else None
    except Exception:
        pass
    if not host:
        host = os.environ.get("WB_HOST_IP", "")
    tok = ""
    for pat in ("/mnt/c/Users/*/.wsl-control/token", "/mnt/c/Users/Public/.wsl-control/token"):
        hits = sorted(glob.glob(pat))
        if hits:
            tok = open(hits[0]).read().strip().replace("\r", "").replace("\n", "")
            break
    return host, tok


def host_ports():
    host, tok = host_8766()
    if not host:
        return {"unavailable": "找不到宿主 IP（ip route 无默认路由，也无 WB_HOST_IP）"}
    url = "http://%s:8766/api/v1/ports" % host
    r = urllib.request.Request(url, headers={"X-Host-Token": tok} if tok else {})
    try:
        with urllib.request.urlopen(r, timeout=8) as resp:
            j = json.loads(resp.read().decode())
            # v2.0.0 响应包一层 data；v1 直接是顶层
            if isinstance(j, dict) and "data" in j and isinstance(j["data"], dict):
                return j["data"]
            return j
    except Exception as e:
        return {"unavailable": "8766 不可达（%s）。看板 http://127.0.0.1:8766/；接入见 wb-base §1.4。" % e}


def port_summary(hp, mapping_id):
    for p in hp.get("ports", []):
        if p.get("id") == mapping_id:
            return p
    return None


# ---------------------------------------------------------------- 命令实现

def cmd_health(ctx, args):
    j = get("/api/health", timeout=10)
    ok = j.get("status") == "ok"
    out(ctx, "%s 8790 /api/health: %s" % ("✅" if ok else "❌", json.dumps(j, ensure_ascii=False)))
    if not ok:
        ctx["exit"] = 1


def cmd_status(ctx, args):
    hp = host_ports()
    if "unavailable" in hp:
        out(ctx, "⚠️ 8766 宿主控制面: %s" % hp["unavailable"])
    else:
        out(ctx, "✅ 8766 宿主控制面（owner / conflict / bridge）:")
        for p in hp.get("ports", []):
            out(ctx, "   %-12s owner=%-13s conflict=%-5s bridge.client_connected=%s"
                % (p.get("id"), p.get("owner"), p.get("conflict"),
                   (p.get("bridge") or {}).get("client_connected")))
    j = get("/api/health", timeout=10)
    out(ctx, "%s 8790 workbench: %s" % ("✅" if j.get("status") == "ok" else "❌", j.get("status")))
    bs = get("/api/serial-bridge/status", timeout=15)
    out(ctx, "桥 all_enabled_ready=%s  ready=%s  unusable=%s"
        % (bs.get("all_enabled_ready"), bs.get("ready_ports"), bs.get("unusable_ports")))
    if bs.get("config_stale"):
        out(ctx, "⚠️ config_stale=true（桥还在用旧配置，重启两侧桥；不要用 SIGHUP）")


def cmd_preflight(ctx, args):
    ok, port, verify = _preflight_port(args.mapping_id, no_open=args.no_open)
    if ok:
        checks = (port or {}).get("checks") or {}
        note = ""
        if checks.get("in_use") and checks.get("open_ok") is None:
            note = "（口被已有会话占用，in_use=true 不阻塞；ensure 时会 409 则等待）"
        out(ctx, "✅ preflight %s: 可过线，可以 ensure/open。%s" % (args.mapping_id, note))
    else:
        out(ctx, "❌ preflight %s: 不可过线，errors=%s（按层级报，别动这个口）" % (args.mapping_id, (port or {}).get("errors")))
        out(ctx, "   原始: %s" % json.dumps(port, ensure_ascii=False))
        ctx["exit"] = 1
    hp = host_ports()
    hp_port = port_summary(hp, args.mapping_id)
    if hp_port:
        out(ctx, "   8766: owner=%s conflict=%s" % (hp_port.get("owner"), hp_port.get("conflict")))
    elif "unavailable" in hp:
        out(ctx, "   8766: %s" % hp["unavailable"])


def _preflight_port(mid, no_open=False):
    """过线判定：只验目标口；usable=enabled+workbench_ready+本口 errors 空；in_use 不算失败。"""
    verify = post("/api/serial-bridge/verify",
                  {"ports": [mid], "open": not no_open}, timeout=30)
    port = None
    for p in verify.get("ports", []):
        if p.get("id") == mid:
            port = p
    if port is None:
        return False, {"id": mid, "errors": ["verify 响应无该口"]}, verify
    errors = port.get("errors") or []
    usable = port.get("usable")
    if usable is None:  # 旧版桥没有 usable 字段，按判据手算
        usable = (port.get("enabled", True) and port.get("workbench_ready") is True and not errors)
    return bool(usable), port, verify


def cmd_auth(ctx, args):
    if not ADMIN_KEY:
        raise WbError("cfg", "缺 WORKBENCH_AI_ADMIN_KEY（签发仅限本机 127.0.0.1 + admin key，见 wb-base §2.1）", 3)
    body = {
        "scopes": [s.strip() for s in args.scopes.split(",") if s.strip()],
        "resources": [r.strip() for r in args.resources.split(",")] if args.resources else ["*"],
        "ttl_seconds": args.ttl,
        "reason": args.reason,
    }
    if args.firmware_root:
        body["firmware_roots"] = [os.path.abspath(os.path.expanduser(p)) for p in args.firmware_root]
    r = urllib.request.Request(BASE + "/api/ai/v1/admin/grants",
                               data=json.dumps(body).encode(), method="POST",
                               headers={"Content-Type": "application/json",
                                        "X-Workbench-Admin-Key": ADMIN_KEY})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            j = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        j = {"http_error": e.code, "detail": e.read().decode()[:300]}
    except Exception as e:
        raise WbError("conn", str(e), 3)
    if "token" not in j:
        out(ctx, "❌ 签发失败: %s" % json.dumps(mask(j), ensure_ascii=False))
        ctx["exit"] = 1
        return
    g = j.get("grant") or {}
    out(ctx, "✅ grant 已签发: grant_id=%s scopes=%s resources=%s firmware_roots=%s ttl=%ss"
        % (g.get("grant_id"), g.get("scopes"), g.get("resources"),
           g.get("firmware_roots"), g.get("expires_at") or body["ttl_seconds"]))
    out(ctx, "TOKEN(只显示这一次，别写进日志/提交；export WORKBENCH_AI_TOKEN=<token> 后本 CLI 自动携带):")
    if ctx.get("json"):
        out(ctx, "TOKEN: ***")  # --json 模式绝不输出裸 token
        ctx["reveal_token"] = j["token"]
    else:
        out(ctx, j["token"])


def _find_session_id(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "session_id" and isinstance(v, str) and v.startswith("ms-"):
                return v
            got = _find_session_id(v)
            if got:
                return got
    elif isinstance(obj, list):
        for x in obj:
            got = _find_session_id(x)
            if got:
                return got
    return None


def cmd_session(ctx, args):
    if args.saction == "stop":
        body = {"action": "stop", "session_id": args.session_id, "force": args.force,
                "client_request_id": args.client_request_id or ("stop-%d" % int(time.time() * 1000))}
        j = post("/api/ai/v2/module-actions", body, timeout=60)
        if j.get("job_state") in ("succeeded", "running", "queued"):
            out(ctx, "✅ 会话已停止%s: %s" % ("（force）" if args.force else "", args.session_id))
            return
        out(ctx, "❌ stop 失败: %s" % json.dumps(mask(j), ensure_ascii=False)[:300])
        if j.get("code") == "409" and not args.force:
            out(ctx, "   409「会话仍有活动观察任务」：先取消观察任务，或加 --force（有先例：force stop 成功）")
        ctx["exit"] = 1
        return
    body = {"action": "ensure", "module": args.module, "mapping_id": args.mapping,
            "client_request_id": args.client_request_id or ("ensure-%s-%d" % (args.mapping, int(time.time() * 1000)))}
    j = post("/api/ai/v2/module-actions", body, timeout=60)
    sid = _find_session_id(j)
    if sid:
        out(ctx, "✅ 会话已确保: session_id=%s（module=%s mapping=%s）" % (sid, args.module, args.mapping))
        out(ctx, "   %s" % json.dumps(mask(j), ensure_ascii=False)[:200])
        return
    if j.get("http_error") == 409:
        out(ctx, "❌ 409 串口占用（物理独占，非 bug）：等待或换口，不硬抢、不并发重试。%s" % json.dumps(j, ensure_ascii=False)[:200])
    else:
        out(ctx, "❌ ensure 失败（响应里没有 session_id）: %s" % json.dumps(mask(j), ensure_ascii=False)[:400])
    ctx["exit"] = 1


def cmd_flash(ctx, args):
    bin_path = os.path.abspath(os.path.expanduser(args.bin))
    name = os.path.basename(bin_path)
    if not os.path.isfile(bin_path):
        raise WbError("usage", "固件不存在: %s" % bin_path, 2)
    if not name.startswith("iap_") and not args.allow_any:
        raise WbError("usage", "只认 iap_*.bin（flash_*.bin 是生产整片，bootloader 不认；upgrade_*.dat 是另一条格式）。"
                               "确认要烧非 iap 件用 --allow-any（仍不推荐）。", 2)
    md5 = hashlib.md5(open(bin_path, "rb").read()).hexdigest()
    size = os.path.getsize(bin_path)
    key = args.client_request_id or ("flash-%s-%s" % (name, md5[:8]))
    if args.new_key:
        key = "flash-%s-%d" % (name, int(time.time() * 1000))
    session_id = args.session
    if not session_id:
        ensure = post("/api/ai/v2/module-actions",
                      {"action": "ensure", "module": args.module, "mapping_id": args.mapping,
                       "client_request_id": "ensure-" + key}, timeout=60)
        session_id = _find_session_id(ensure)
        if not session_id:
            out(ctx, "❌ 先取会话失败（409=串口占用，别硬抢）: %s" % json.dumps(mask(ensure), ensure_ascii=False)[:300])
            ctx["exit"] = 1
            return
    out(ctx, "件: %s" % bin_path)
    out(ctx, "   md5=%s  bytes=%d  slot=%s  client_request_id=%s" % (md5, size, args.slot, key))
    out(ctx, "   session_id=%s" % session_id)
    j = post("/api/ai/v2/flash-jobs",
             {"session_id": session_id, "bin_path": bin_path, "slot": args.slot,
              "client_request_id": key}, timeout=300)
    job_id = j.get("job_id")
    if not job_id:
        if j.get("http_error") == 403:
            out(ctx, "❌ 403 授权白名单：签发时带 firmware_roots（wb auth --firmware-root <目录>），"
                     "或启动时配 WORKBENCH_AI_FIRMWARE_ROOTS。这是授权来源问题，不是缺陷；"
                     "禁止重启工作台塞 env 绕过。%s" % json.dumps(j, ensure_ascii=False)[:300])
        else:
            out(ctx, "❌ 提交失败: %s" % json.dumps(mask(j), ensure_ascii=False)[:400])
        ctx["exit"] = 1
        return
    out(ctx, "✅ 已受理（异步，0.13s 量级返回）: job_id=%s job_state=%s" % (job_id, j.get("job_state")))
    out(ctx, "   等结果: python3 %s wait %s   （不要重提催结果；verdict 恒 null，烧成没成看 wait 的归因与横幅）"
        % (os.path.abspath(__file__), job_id))


def _attribution(ctx, job):
    """失败归因，按 wb-base §3.4 口径：①steps.reason ②sent_hex ③L1 ④operations.json。"""
    out(ctx, "—— 失败归因（按 §3.4 顺序）——")
    res = ((job.get("result") or {}).get("result") or {})
    steps = res.get("steps") or []
    shown = False
    for s in steps:
        if s.get("result") in ("fail", "error", None) and (s.get("reason") or s.get("sent_hex") is not None or True):
            sent = s.get("sent_hex")
            if s.get("result") not in ("pass",):
                shown = True
                out(ctx, "① step[%s] result=%s reason=%s" % (s.get("name") or s.get("index"), s.get("result"), s.get("reason")))
                if sent == "" or sent is None:
                    out(ctx, "   sent_hex 为空 = 根本没发出去，不是「没收到回应」")
    if not shown:
        out(ctx, "① result.steps 无失败步信息")
    try:
        ev = get("/api/ai/v2/jobs/%s/evidence?level=L1" % job.get("job_id"), timeout=30)
        items = ev.get("items") or []
        if items:
            out(ctx, "③ L1 证据 %d 条，首条: %s" % (len(items), json.dumps(items[0], ensure_ascii=False)[:300]))
        else:
            out(ctx, "③ L1 证据 items:[]（证据全空 ≠ 没原因，看 ④）")
    except Exception as e:
        out(ctx, "③ L1 读取失败: %s" % e)
    op_id = None
    refs = job.get("underlying_refs") or []
    if refs:
        op_id = refs[0] if isinstance(refs[0], str) else (refs[0] or {}).get("operation_id")
    op_id = op_id or (job.get("result") or {}).get("underlying_operation_id")
    root = workbench_root()
    if op_id and root:
        ops_path = os.path.join(root, "apps", "workbench", "runtime", "ai-control", "operations.json")
        if os.path.isfile(ops_path):
            try:
                data = json.load(open(ops_path))
                entries = data if isinstance(data, list) else data.get("operations") or []
                for e in entries:
                    if e.get("operation_id") == op_id or e.get("id") == op_id:
                        out(ctx, "④ operations.json op=%s error=%s" % (op_id, e.get("error")))
                        break
                else:
                    out(ctx, "④ operations.json 里没找到 op=%s（文件: %s）" % (op_id, ops_path))
            except Exception as e:
                out(ctx, "④ operations.json 解析失败: %s" % e)
        else:
            out(ctx, "④ operations.json 不存在: %s" % ops_path)
    else:
        out(ctx, "④ 无 underlying op id%s，跳过 operations.json" % ("" if root else "、无 WORKBENCH_ROOT"))


def cmd_wait(ctx, args):
    deadline = time.time() + args.timeout
    last = None
    while True:
        remain = max(1, min(30, int(deadline - time.time())))
        j = get("/api/ai/v2/jobs/%s?wait_seconds=%d" % (args.job_id, remain), timeout=remain + 20)
        state = j.get("job_state")
        if state != last:
            out(ctx, "[%s] job_state=%s" % (time.strftime("%H:%M:%S"), state))
            last = state
        if state in TERMINAL:
            break
        if time.time() >= deadline:
            out(ctx, "⏱ 等待超过 %ds 仍未终态（job_state=%s）。烧录不可取消、不可重试——继续用本命令等，"
                     "或看会话日志；别重提、别断电。" % (args.timeout, state))
            ctx["exit"] = 1
            return
    summary = j.get("summary") or ""
    if j.get("job_state") == "succeeded":
        out(ctx, "✅ 终态 succeeded。summary=%s" % summary)
        out(ctx, "   注意：succeeded 只代表任务跑完。烧录是否真成：看会话日志 [EVENT] 烧录完成：BURN SUCCESS "
                 "+ 包数全等 + 烧后六行横幅（判据表见 wb-flash §5）；verification_run 的 summary 带 pass/fail 才是业务判定。")
    else:
        out(ctx, "❌ 终态 %s。summary=%s" % (j.get("job_state"), summary))
        _attribution(ctx, j)
        ctx["exit"] = 1


def cmd_evidence(ctx, args):
    j = get("/api/ai/v2/jobs/%s/evidence?level=%s" % (args.job_id, args.level), timeout=30)
    if ctx.get("json"):
        out(ctx, json.dumps(mask(j), ensure_ascii=False))
        return
    items = j.get("items") or []
    out(ctx, "level=%s  %d 条" % (args.level, len(items)))
    for it in items[:args.limit]:
        out(ctx, "  %s" % json.dumps(it, ensure_ascii=False)[:400])


# ---------------------------------------------------------------- wb flash run（一条命令编排整条烧录链）

def _latest_bin(repo):
    """读工程根 latest_flash.json（build_variants.sh 打包后生成），取最新产物。"""
    p = os.path.join(repo, "latest_flash.json")
    if not os.path.isfile(p):
        raise WbError("usage", "未找到 %s（由 build_variants.sh 编译后生成）；请先编译或改用 --bin 指定。" % p, 2)
    j = json.load(open(p))
    art = j.get("latest") or (j.get("artifacts") or [None])[-1]
    if not art or not os.path.isfile(art.get("bin_path", "")):
        raise WbError("usage", "latest_flash.json 里的产物不存在: %s" % art, 2)
    return art["bin_path"], art


def _find_session_log(root, module, mapping, since_ts):
    d = os.path.join(root, "data", "logs", "模块", module)
    best = None
    for f in glob.glob(os.path.join(d, "*.log")):
        st = os.stat(f)
        if st.st_mtime >= since_ts - 5 and mapping in os.path.basename(f):
            if best is None or st.st_mtime > os.stat(best).st_mtime:
                best = f
    return best


def _judge_burn(log_path, bin_path):
    """wb-flash §5 判定表固化：BURN SUCCESS / 包数全等 / 烧后横幅 / 件名比对。"""
    text = open(log_path, encoding="utf-8", errors="replace").read()
    res = {"burn_success": "BURN SUCCESS" in text}
    ms = re.findall(r"packet=(\d+)/(\d+) bytes=(\d+)/(\d+) pct=(\d+)", text)
    if ms:
        m = ms[-1]  # 取最后一次 progress（终值），不是首条
        res["packet"] = {"sent": int(m[0]), "total": int(m[1]),
                         "bytes_sent": int(m[2]), "bytes_total": int(m[3]),
                         "pct": int(m[4]),
                         "全等": int(m[0]) == int(m[1]) and int(m[2]) == int(m[3])}
    banner = {}
    idx = text.rfind("boot_ver")  # 烧后自动重启的横幅在日志最后
    if idx >= 0:
        seg = text[idx:idx + 900]
        for key, pat in (("boot_ver", r"boot_ver\s*[:：]\s*(\S+)"),
                         ("sdk_ver", r"sdk_ver\s*[:：]\s*(\S+)"),
                         ("hver", r"hver\s*[:：]?\s*([0-9a-fA-F]{4,6})"),
                         ("sver", r"sver\s*[:：]?\s*([0-9a-fA-F]{4,6})"),
                         ("isv_date", r"isv date\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")):
            mm = re.search(pat, seg)
            if mm:
                banner[key] = mm.group(1).rstrip(",")
        mm = re.search(r"\bisv\s*[:：]\s*([0-9a-fA-F]{6})\b", seg)  # 不会误吃 "isv date:"
        if mm:
            banner["isv"] = mm.group(1)
    res["banner"] = banner
    # 件名 ↔ 横幅比对
    name = os.path.basename(bin_path)
    checks, unmatched = [], []
    for field, namepat, norm in (
            ("hver", r"hv(\d{4})", None),
            ("sver", r"sv(\d{4,6})", None),
            ("isv", r"isv(\d{6})", None),
            ("isv_date", r"idate(\d{6})", lambda v: "20%s-%s-%s" % (v[:2], v[2:4], v[4:6]))):
        nm = re.search(namepat, name)
        if not nm:
            continue
        name_val = nm.group(1)
        ban_val = banner.get(field)
        if ban_val is None:
            unmatched.append({"件名字段": name_val, "字段": field, "原因": "横幅无对应项"})
            continue
        a = norm(name_val) if norm else name_val
        checks.append({"字段": field, "件名": a, "横幅": ban_val, "命中": a == ban_val})
    dm = re.search(r"(?<!i)date(\d{6})", name)  # 大版本日期（排除 idate）
    if dm:
        unmatched.append({"件名字段": dm.group(1), "字段": "date", "原因": "横幅无对应字段"})
    fm = re.search(r"FC_([0-9A-Za-z]+)", name)
    if fm:
        unmatched.append({"件名字段": "FC_" + fm.group(1), "字段": "FC", "原因": "横幅无对应字段"})
    res["件名比对"] = {"checks": checks,
                     "命中数": sum(1 for c in checks if c["命中"]),
                     "可比数": len(checks),
                     "横幅无对应字段": unmatched}
    return res


def _audit_flash_authorization(bin_path):
    key = os.environ.get("WORKBENCH_AI_ADMIN_KEY", "")
    if not key:
        return {"skipped": "环境无 WORKBENCH_AI_ADMIN_KEY，跳过审计核验（放行本身已有服务端审计）"}
    body = json.dumps({"scopes": ["status:read"], "resources": ["*"],
                       "ttl_seconds": 600, "reason": "wb flash run 审计核验"}).encode()
    r = urllib.request.Request(BASE + "/api/ai/v1/admin/grants", data=body, method="POST",
                               headers={"Content-Type": "application/json",
                                        "X-Workbench-Admin-Key": key})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            tok = json.loads(resp.read().decode()).get("token")
    except Exception as e:
        return {"skipped": "签发审计查询用 grant 失败: %s" % e}
    r2 = urllib.request.Request(BASE + "/api/ai/v1/audit?limit=500",
                                headers={"Authorization": "Bearer " + (tok or "")})
    try:
        with urllib.request.urlopen(r2, timeout=20) as resp:
            entries = json.loads(resp.read().decode()).get("entries") or []
    except Exception as e:
        return {"skipped": "audit 查询失败: %s" % e}
    hit = None
    for e in entries:
        if e.get("action") != "flash.authorization":
            continue
        d = e.get("details") or {}
        r = e.get("result")
        if isinstance(r, str):  # 实测 result 是 JSON 字符串
            try:
                r = json.loads(r)
            except Exception:
                r = {}
        r = r or {}
        bp = d.get("bin_path") or r.get("bin_path")
        if bp == bin_path:
            hit = e  # 同件多次烧录时取最后一条（entries 按时间正序）
    if hit:
        d = hit.get("details") or {}
        r = hit.get("result")
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except Exception:
                r = {}
        r = r or {}
        return {"found": True,
                "authorization_source": d.get("authorization_source") or r.get("authorization_source"),
                "operation_id": hit.get("operation_id")}
    return {"found": False, "note": "近 %d 条审计里未找到本次放行记录" % len(entries)}


def cmd_flash_run(ctx, args):
    t0 = time.time()
    started = time.strftime("%Y%m%d-%H%M")
    res = {"verdict": None, "target": {"mapping_id": args.mapping, "module": args.module}}
    steps = res["steps"] = []

    # ① 选件
    if args.bin:
        bin_path = os.path.abspath(os.path.expanduser(args.bin))
        latest_meta = None
    elif args.latest:
        bin_path, latest_meta = _latest_bin(os.path.abspath(os.path.expanduser(args.latest)))
    else:
        raise WbError("usage", "需要 --bin <iap 路径> 或 --latest <工程根>", 2)
    if not os.path.isfile(bin_path):
        raise WbError("usage", "固件不存在: %s" % bin_path, 2)
    name = os.path.basename(bin_path)
    if not name.startswith("iap_"):
        res["verdict"], res["error"] = "rejected", "只认 iap_*.bin（flash_*.bin bootloader 不认，upgrade_*.dat 是另一格式）"
        print(json.dumps(res, ensure_ascii=False, indent=2))
        ctx["exit"] = 1
        return
    md5 = hashlib.md5(open(bin_path, "rb").read()).hexdigest()
    total = os.path.getsize(bin_path)
    res["bin"] = {"path": bin_path, "md5": md5, "bytes": total, "name": name}
    if latest_meta:
        res["bin"]["from_latest_json"] = {k: latest_meta.get(k) for k in ("variant", "sversion", "fc_version_l")}

    # ② preflight
    ok, port, verify = _preflight_port(args.mapping)
    steps.append({"step": "preflight", "ok": ok, "detail": port})
    if not ok:
        res["verdict"] = "preflight_failed"
        res["hint"] = "目标口不可过线（errors 见 steps），等待/换口，别硬抢"
        print(json.dumps(res, ensure_ascii=False, indent=2))
        ctx["exit"] = 1
        return

    # ③ ensure 会话（键用时间戳保证唯一；md5 派生键只属于 flash 提交，回放旧会话会引发 409）
    ens = post("/api/ai/v2/module-actions",
               {"action": "ensure", "module": args.module, "mapping_id": args.mapping,
                "client_request_id": "ensure-%s-%d" % (args.mapping, int(time.time() * 1000))}, timeout=60)
    sid = _find_session_id(ens)
    steps.append({"step": "ensure", "ok": bool(sid), "session_id": sid})
    if not sid:
        res["verdict"] = "ensure_failed"
        res["detail"] = mask(ens)
        res["hint"] = "409=串口占用（物理独占），等待或换口；不硬抢"
        print(json.dumps(res, ensure_ascii=False, indent=2))
        ctx["exit"] = 1
        return
    res["session_id"] = sid

    # ④ 提交（幂等键 md5 派生；同件重提复用原 job，防二次烧录）
    # ④ 提交（幂等键 md5 派生；同件重提复用原 job，防二次烧录；--new-key 仅在明确要重烧同件时用）
    key = ("flash-%s-%d" % (name, int(time.time() * 1000))) if args.new_key else ("flash-%s-%s" % (name, md5[:8]))
    job = post("/api/ai/v2/flash-jobs",
               {"session_id": sid, "bin_path": bin_path, "slot": args.slot,
                "client_request_id": key}, timeout=300)
    job_id = job.get("job_id")
    idempotent_replay = False
    if not job_id and job.get("http_error") == 409 and "幂等键" in str(job.get("message", "")):
        # 同键已有历史提交（同件此前烧过、会话不同）：找回既有 job 走判定回放，不重烧
        lst = get("/api/ai/v2/jobs?kind=flash_job&limit=100", timeout=30)
        found = None
        for j in lst.get("jobs", []):
            if j.get("client_request_id") == key:
                found = j
                break
        if found:
            job_id = found.get("job_id")
            job = get("/api/ai/v2/jobs/%s?wait_seconds=1" % job_id, timeout=30)
            idempotent_replay = True
            steps.append({"step": "submit", "ok": True, "job_id": job_id, "note": "409 幂等键冲突 → 回放既有 job，未重新烧录"})
    steps.append({"step": "submit", "ok": bool(job_id), "job_id": job_id, "http": job.get("http_error")})
    if not job_id:
        res["verdict"] = "submit_failed"
        res["detail"] = mask(job)
        if job.get("http_error") == 403:
            res["hint"] = "403 授权白名单：签发带 firmware_roots 的 grant 或启动配 WORKBENCH_AI_FIRMWARE_ROOTS；禁止重启工作台塞 env 绕过"
        elif job.get("http_error") == 409:
            res["hint"] = "409 幂等键冲突且列表未找到既有 job（limit=100 窗口外）：确认要重烧用 --new-key 提交"
        print(json.dumps(res, ensure_ascii=False, indent=2))
        ctx["exit"] = 1
        return
    res["job_id"] = job_id
    if not idempotent_replay and job.get("job_state") in TERMINAL:
        idempotent_replay = True  # 服务端同键直接回放既有终态 job（秒回，不可能是新烧）

    # ⑤ 等终态
    deadline = time.time() + args.timeout
    while True:
        remain = max(1, min(30, int(deadline - time.time())))
        job = get("/api/ai/v2/jobs/%s?wait_seconds=%d" % (job_id, remain), timeout=remain + 20)
        state = job.get("job_state")
        if state in TERMINAL or time.time() >= deadline:
            break
    res["job_state"] = state
    res["duration_seconds"] = round(time.time() - t0, 1)
    if time.time() < deadline and state not in TERMINAL:
        res["verdict"], res["hint"] = "timeout", "等待超时仍未终态：继续用 wb wait 等，别重提别断电"
        print(json.dumps(res, ensure_ascii=False, indent=2))
        ctx["exit"] = 1
        return

    # ⑥ 判定（wb-flash §5 固化）
    root = workbench_root()
    log_path = _find_session_log(root, args.module, args.mapping, t0) if root else None
    res["session_log"] = log_path
    if idempotent_replay:
        res["idempotent_replay"] = True
        res["verdict"] = "flash_ok" if state == "succeeded" else "flash_" + state
        res["note"] = "幂等键命中历史 job（%s），本次未重新烧录；判定基于该 job 历史终态" % job_id
    elif state == "succeeded":
        if log_path:
            res.update(_judge_burn(log_path, bin_path))
            # 横幅滞后：设备重启打横幅可能晚于 BURN SUCCESS 落日志，先安静等
            waited = 0
            while not res.get("banner") and waited < args.banner_wait:
                time.sleep(2)
                waited += 2
                res.update(_judge_burn(log_path, bin_path))
            # 仍缺 → 自动补采：同会话空行自证 shell 后 reboot，等横幅（复测先例：空行→提示符→reboot→六行横幅）
            if not res.get("banner") and not args.keep_session:
                steps.append({"step": "banner_reboot", "note": "BURN SUCCESS 后会话日志未见横幅，自动补采（空行自证→reboot）"})
                post("/api/ai/v2/module-actions",
                     {"action": "send", "session_id": sid, "text": "", "append_newline": True,
                      "client_request_id": "banner-empty-%d" % int(time.time() * 1000)}, timeout=30)
                time.sleep(1.5)
                post("/api/ai/v2/module-actions",
                     {"action": "send", "session_id": sid, "text": "reboot", "append_newline": True,
                      "client_request_id": "banner-reboot-%d" % int(time.time() * 1000)}, timeout=30)
                waited = 0
                while not res.get("banner") and waited < args.banner_wait * 2:
                    time.sleep(2)
                    waited += 2
                    res.update(_judge_burn(log_path, bin_path))
            cmpj = res.get("件名比对", {})
            all_ok = (res.get("burn_success") and (res.get("packet") or {}).get("全等")
                      and cmpj.get("可比数") and cmpj.get("命中数") == cmpj.get("可比数"))
            res["verdict"] = "flash_ok" if all_ok else "flash_unverified"
            if res["verdict"] == "flash_unverified":
                res["hint"] = "任务 succeeded 但判定项不全（缺 BURN SUCCESS / 包数不全等 / 横幅或件名比对未全中），人工核对 session_log；已自动尝试等待与 reboot 补采"
        else:
            res["verdict"] = "flash_unverified"
            res["hint"] = "succeeded 但找不到会话日志（WORKBENCH_ROOT 未解析？），人工判定"
    else:
        res["verdict"] = "flash_failed"
        res["summary"] = job.get("summary")
        attr_ctx = {"lines": []}
        _attribution(attr_ctx, job)
        res["attribution"] = attr_ctx["lines"]
        if "Bootloader prompt was not detected" in str(res.get("summary", "")):
            res["hint"] = "先空行自证 shell（有提示符回显）再重试；同口同件一败一成有先例（wb-flash 坑4），别急着定性纯日志口"

    # ⑦ 证据落盘（wb-flash §6 清单）
    ev_dir = None
    if root:
        ev_dir = os.path.join(root, "evidence", "run", "flash-%s-%s" % (args.module, started))
        try:
            os.makedirs(ev_dir, exist_ok=True)
            open(os.path.join(ev_dir, "01-firmware-md5.txt"), "w").write("%s  %s  %d bytes\n" % (md5, bin_path, total))
            json.dump(steps, open(os.path.join(ev_dir, "02-steps.json"), "w"), ensure_ascii=False, indent=2)
            open(os.path.join(ev_dir, "03-job-final.json"), "w").write(json.dumps(mask(job), ensure_ascii=False, indent=2))
            if log_path:
                open(os.path.join(ev_dir, "04-session-log-orig.log"), "wb").write(open(log_path, "rb").read())
            open(os.path.join(ev_dir, "README.md"), "w").write(
                "# 烧录判定（wb flash run 自动生成）\n\n- verdict: **%s**\n- 件: %s (md5 %s, %d B)\n- 口: %s (mapping %s)\n"
                "- job: %s  终态: %s  耗时: %ss\n- 判定: %s\n- 会话日志: %s\n"
                % (res["verdict"], name, md5, total, args.mapping, args.mapping, job_id, state,
                   res["duration_seconds"], json.dumps({k: v for k, v in res.items() if k in ("burn_success", "packet", "banner", "件名比对")}, ensure_ascii=False),
                   log_path or "未找到"))
            res["evidence_dir"] = ev_dir
        except Exception as e:
            res["evidence_error"] = str(e)

    # ⑧ 审计核验（尽力而为）
    if state == "succeeded":
        res["audit"] = _audit_flash_authorization(bin_path)

    # ⑨ 释放串口（409 时 force 兜底）
    if not args.keep_session:
        st = post("/api/ai/v2/module-actions",
                  {"action": "stop", "session_id": sid, "force": False,
                   "client_request_id": "stop-" + key}, timeout=60)
        if st.get("job_state") not in ("succeeded", "running", "queued"):
            st = post("/api/ai/v2/module-actions",
                      {"action": "stop", "session_id": sid, "force": True,
                       "client_request_id": "stop-force-" + key}, timeout=60)
        res["session_stop"] = "ok" if st.get("job_state") in ("succeeded", "running", "queued") else mask(st)

    print(json.dumps(res, ensure_ascii=False, indent=2))
    ctx["exit"] = 0 if res["verdict"] == "flash_ok" else 1




def build_parser():
    p = argparse.ArgumentParser(prog="wb", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="输出 JSON（token 字段仍遮蔽），不打印人读结论")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("health", help="8790 探活")
    s.set_defaults(fn=cmd_health)

    s = sub.add_parser("status", help="8766 + 8790 + 串口桥一屏")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("preflight", help="开串口前过线判定（只验目标口）")
    s.add_argument("mapping_id")
    s.add_argument("--no-open", action="store_true", help="跳过打开检查")
    s.set_defaults(fn=cmd_preflight)

    s = sub.add_parser("auth", help="签最小权限 grant")
    s.add_argument("--scopes", required=True, help="逗号分隔，如 module_flash:execute,module_session:ensure,evidence:read")
    s.add_argument("--reason", required=True)
    s.add_argument("--resources", default="*", help="逗号分隔；默认 *（谨慎）")
    s.add_argument("--firmware-root", nargs="*", help="烧录必给：允许烧录目录白名单")
    s.add_argument("--ttl", type=int, default=3600)
    s.set_defaults(fn=cmd_auth)

    s = sub.add_parser("session", help="模块串口会话")
    ssub = s.add_subparsers(dest="saction", required=True)
    e = ssub.add_parser("ensure")
    e.add_argument("module", choices=FLASH_HOSTS)
    e.add_argument("--mapping", required=True, help="mapping_id，不硬编码 COM 号")
    e.add_argument("--client-request-id")
    e.set_defaults(fn=cmd_session)
    st = ssub.add_parser("stop")
    st.add_argument("session_id", help="ms-xxxx")
    st.add_argument("--force", action="store_true",
                    help="409「会话仍有活动观察任务」时用（先例：force stop 成功）")
    st.add_argument("--client-request-id")
    st.set_defaults(fn=cmd_session)

    s = sub.add_parser("flash", help="烧录")
    ssub = s.add_subparsers(dest="faction", required=True)
    f = ssub.add_parser("submit")
    f.add_argument("bin")
    f.add_argument("--module", choices=FLASH_HOSTS, default="sta")
    f.add_argument("--mapping", help="不给则按 module 默认 cco-main/sta-main")
    f.add_argument("--session", help="已有 ms-xxxx；不给则自动 ensure")
    f.add_argument("--slot", type=int, default=0)
    f.add_argument("--client-request-id")
    f.add_argument("--new-key", action="store_true", help="强制新幂等键（仅在确认要重烧时用）")
    f.add_argument("--allow-any", action="store_true", help="允许非 iap_ 件名（不推荐）")
    f.set_defaults(fn=cmd_flash)

    r = ssub.add_parser("run", help="一条命令编排整条烧录链，输出单个 JSON 判定（主路径）")
    r.add_argument("--bin", help="iap 固件路径")
    r.add_argument("--latest", help="工程根：读其 latest_flash.json（build_variants.sh 生成）取最新件")
    r.add_argument("--module", choices=FLASH_HOSTS, default="sta")
    r.add_argument("--mapping", help="不给则按 module 默认 cco-main/sta-main")
    r.add_argument("--slot", type=int, default=0)
    r.add_argument("--timeout", type=int, default=420, help="等终态总时长（秒）")
    r.add_argument("--new-key", action="store_true",
                   help="同件真重烧（默认同件重提=回放既有 job，不重烧；重烧需人明确要求）")
    r.add_argument("--banner-wait", type=int, default=25,
                   help="BURN SUCCESS 后等横幅的秒数；仍缺则同会话自动 reboot 补采")
    r.add_argument("--keep-session", action="store_true", help="烧完不释放会话（默认释放）")
    r.set_defaults(fn=cmd_flash_run)

    s = sub.add_parser("wait", help="等 job 终态，失败自动归因")
    s.add_argument("job_id")
    s.add_argument("--timeout", type=int, default=600)
    s.set_defaults(fn=cmd_wait)

    s = sub.add_parser("evidence", help="读证据")
    s.add_argument("job_id")
    s.add_argument("--level", choices=["L1", "L2", "L3"], default="L1")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(fn=cmd_evidence)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    json_flag = False
    while "--json" in argv:  # --json 任意位置可用（全局选项，避免 argparse 子命令作用域坑）
        json_flag = True
        argv.remove("--json")
    args = build_parser().parse_args(argv)
    if getattr(args, "mapping", None) is None and args.cmd == "flash":
        args.mapping = "cco-main" if args.module == "cco" else "sta-main"
    ctx = {"lines": [], "exit": 0, "json": json_flag}
    try:
        args.fn(ctx, args)
    except WbError as e:
        print("❌ %s" % e, file=sys.stderr)
        return e.exit_code
    if json_flag:
        print(json.dumps({"exit": ctx["exit"], "lines": ctx["lines"]}, ensure_ascii=False))
    elif ctx["lines"]:
        flush(ctx)
    return ctx["exit"]


if __name__ == "__main__":
    sys.exit(main())
