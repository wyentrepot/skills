#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flash.py — 海思 DW31 在线升级【一条命令】入口
=================================================
AI 只需要两个输入：--project（工程根路径）+ --file（升级包文件）。
脚本内部完成：doctor → prepare → commit → 轮询进度 → 等模块重启回连
→ 自动同步宿主 prim XML → 激活核对，最后**只在 stdout 打一份 JSON**。

    python3 flash.py --project /home/H_HS/GW/plc-project \
                     --file out/sg_fusion_cco/bin/DW31v100_mcore_sg_cco_upg.bin

退出码：0 = 升级成功且已回连；非 0 = 失败（JSON 里 ok=false + failed_at + error）。

其它可用参数（都有默认值，正常不用给）：
  --xml PATH|auto|none   宿主 prim 库（默认 auto：找工程构建产物）
  --dry-run              只 prepare 不烧
  --timeout SEC          烧录轮询上限（默认 300）
  --json-out PATH        额外把 JSON 落盘
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FCCTL = os.environ.get(
    "FCCTL",
    os.path.join(SKILL_ROOT, "..", "hs-dw31-base", "scripts", "fcctl.py"),
)
CURL = "/mnt/c/Windows/System32/curl.exe"
BASE8765 = os.environ.get("FC_BASE", "http://127.0.0.1:8765")


# ----------------------------------------------------------------- 基础工具
def now():
    return time.strftime("%H:%M:%S")


def run_ctl(*args, timeout=90):
    """调 fcctl.py，返回解析后的 dict。"""
    cmd = [sys.executable, FCCTL] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": {"code": "TIMEOUT", "message": f"fcctl {args} 超时"}}
    out = (r.stdout or "").strip()
    try:
        return json.loads(out)
    except Exception:
        return {
            "ok": False,
            "error": {
                "code": "CLI_PARSE_FAILED",
                "message": (out or r.stderr or "")[:400],
            },
        }


def http_json(method, path, payload=None, timeout=30):
    """直连 8765（WSL 用 Windows curl.exe）。"""
    body = json.dumps(payload) if payload is not None else ""
    if os.path.isfile(CURL):
        cmd = [CURL, "-sS", "--max-time", str(timeout), "-X", method,
               "-H", "Content-Type: application/json", "-d", body, BASE8765 + path]
    else:  # 兜底：服务在 WSL 内可达时
        import urllib.request
        req = urllib.request.Request(
            BASE8765 + path, data=body.encode() or None, method=method,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        return json.loads(r.stdout) if r.stdout.strip() else {"ok": False,
                                                              "error": {"code": "EMPTY"}}
    except Exception as e:
        return {"ok": False, "error": {"code": "HTTP_FAILED", "message": str(e)}}


def post_json_big(path, payload, timeout=180):
    """大 body（xml_hex 可达数百 KB）写临时文件后 curl -d @file，避开 ARG_MAX。"""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        if os.path.isfile(CURL):
            cmd = [CURL, "-sS", "--max-time", str(timeout), "-X", "POST",
                   "-H", "Content-Type: application/json",
                   "-d", "@" + to_win_path(tmp), BASE8765 + path]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 20)
            return json.loads(r.stdout) if r.stdout.strip() else {"ok": False,
                                                                  "error": {"code": "EMPTY"}}
        import urllib.request
        req = urllib.request.Request(BASE8765 + path, data=json.dumps(payload).encode(),
                                     method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"ok": False, "error": {"code": "HTTP_FAILED", "message": str(e)}}
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def to_win_path(p):
    """WSL 路径 → Windows 可读路径（服务跑在 Windows 侧）。"""
    try:
        r = subprocess.run(["wslpath", "-w", p], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    real = os.path.realpath(p)
    if real.startswith("/mnt/") and len(real) > 6:
        return real[5].upper() + ":" + real[6:].replace("/", "\\")
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu-22.04")
    return "\\\\wsl.localhost\\" + distro + real.replace("/", "\\")


# ----------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="海思 DW31 在线升级（一条命令出 JSON）")
    ap.add_argument("--project", help="工程根路径（含 scripts/build.sh）；给了绝对 --file 可省")
    ap.add_argument("--file", required=True, help="升级包文件（绝对路径，或相对 --project）")
    ap.add_argument("--xml", default="auto", help="auto|none|<prim xml 路径>")
    ap.add_argument("--struct", default="auto", choices=["auto", "none"],
                    help="是否随 XML 上传结构体定义（默认 auto）")
    ap.add_argument("--dry-run", action="store_true", help="只 prepare 不烧")
    ap.add_argument("--timeout", type=int, default=300, help="烧录轮询上限秒")
    ap.add_argument("--json-out", help="额外落盘路径")
    a = ap.parse_args()

    t_start = time.time()
    res = {
        "ok": False,
        "step": "init",
        "started_at": now(),
        "inputs": {"project": a.project, "file": a.file},
    }

    def fail(step, err):
        res.update(ok=False, step=step, failed_at=now(), error=err,
                   elapsed_s=round(time.time() - t_start, 1))
        emit(res, a.json_out)
        sys.exit(1)

    # ---- 1 解析路径与包 ----
    pkg = a.file
    if not os.path.isabs(pkg):
        if not a.project:
            fail("resolve", {"code": "BAD_INPUT", "message": "相对 --file 必须同时给 --project"})
        pkg = os.path.join(a.project, pkg)
    pkg = os.path.abspath(pkg)
    if not os.path.isfile(pkg):
        fail("resolve", {"code": "PACKAGE_NOT_FOUND", "message": pkg})

    project = a.project
    if not project:
        d = os.path.dirname(pkg)
        while d and d != "/":
            if os.path.isfile(os.path.join(d, "scripts", "build.sh")):
                project = d
                break
            d = os.path.dirname(d)
    res["inputs"].update(project=project, package=pkg,
                         package_size=os.path.getsize(pkg))

    # ---- 2 设备就绪 ----
    res["step"] = "doctor"
    d = run_ctl("doctor")
    if not d.get("ok"):
        fail("doctor", d.get("error", d))
    data = d.get("data", {})
    if not (data.get("legacy") or {}).get("device_ready"):
        fail("doctor", {"code": "DEVICE_NOT_READY",
                        "message": (data.get("legacy") or {}).get("error")})
    st = (data.get("legacy", {}).get("state") or {})
    res["before"] = {"module_ver": st.get("module_ver"),
                     "reconnect_count": st.get("reconnect_count")}

    # ---- 3 prepare ----
    res["step"] = "prepare"
    p = run_ctl("flash-prepare", pkg, timeout=120)
    if not (p.get("ok") and p.get("data", {}).get("ok")):
        fail("prepare", p.get("error", p))
    pd = p["data"]
    res["package"] = {
        "path": pd.get("package", {}).get("path"),
        "size": pd.get("package", {}).get("size"),
        "sha256": pd.get("package", {}).get("sha256"),
        "approval_id": pd.get("approval_id"),
    }
    res["before"]["target_version"] = (pd.get("target") or {}).get("current_version")
    res["before"]["module_mac"] = (pd.get("target") or {}).get("module_mac")

    if a.dry_run:
        res.update(ok=True, step="dry-run",
                   note="只 prepare，未烧录", elapsed_s=round(time.time() - t_start, 1))
        emit(res, a.json_out)
        sys.exit(0)

    # ---- 4 commit ----
    res["step"] = "commit"
    c = run_ctl("flash-commit", "--approval-id", pd["approval_id"],
                "--user-approval",
                "AI 按用户指令执行在线升级：%s（%s）" % (os.path.basename(pkg), a.file),
                timeout=60)
    if not (c.get("ok") and c.get("data", {}).get("ok")):
        fail("commit", c.get("error", c))

    # ---- 5 轮询烧录进度 ----
    res["step"] = "flashing"
    t0 = time.time()
    last = {}
    while time.time() - t0 < a.timeout:
        time.sleep(3)
        s = run_ctl("flash-status", timeout=30)
        sm = ((s.get("data") or {}).get("summary") or {})
        if sm:
            last = sm
        state = sm.get("state")
        if state in ("DONE", "FAILED", "ERROR", "STOPPED", "ABORTED"):
            break
    res["flash"] = {
        "state": last.get("state"),
        "percent": last.get("percent"),
        "blocks": "%s/%s" % (last.get("sent"), last.get("total")),
        "rcv_file_size": last.get("rcv_file_size"),
        "upg_status_text": last.get("upg_status_text"),
        "error_code": last.get("error_code"),
        "seconds": round(time.time() - t0, 1),
    }
    if last.get("state") != "DONE":
        fail("flashing", {"code": "FLASH_NOT_DONE", "message": res["flash"]})

    # ---- 6 等模块回连 ----
    res["step"] = "wait_reconnect"
    t0 = time.time()
    reconnected = False
    while time.time() - t0 < 180:
        time.sleep(5)
        s = run_ctl("status", timeout=30)
        sd = s.get("data") or {}
        if sd.get("logged_in") and sd.get("device_cmd_ok"):
            reconnected = True
            res["after"] = {"module_ver": sd.get("module_ver"),
                            "reconnect_count": sd.get("reconnect_count"),
                            "reconnect_seconds": round(time.time() - t0, 1)}
            break
    if not reconnected:
        fail("wait_reconnect", {"code": "NO_RECONNECT", "message": "模块复位后 180s 未回连"})

    # ---- 7 上传/同步宿主 prim 库（改过日志 id 必须做） ----
    res["step"] = "sync_prim"
    xml = None
    if a.xml == "none":
        res["prim"] = {"synced": False, "reason": "--xml none"}
    else:
        if a.xml != "auto":
            xml = os.path.abspath(a.xml)
        elif project:
            xml = os.path.join(
                project, "Platform", "plc-sdk", "out", "DW31v100", "database_sg",
                "cco", "system", "hdbcfg", "mss_prim_db.xml")
        if not (xml and os.path.isfile(xml)):
            res["prim"] = {"synced": False, "reason": "找不到 prim xml", "xml": xml}
        else:
            # 结构体定义随 XML 一起上传，否则结构树为空
            struct = os.path.normpath(os.path.join(
                os.path.dirname(os.path.dirname(xml)),
                "diag", "main_core_mak_msg_struct_def.txt"))
            payload = {"xml_hex": open(xml, "rb").read().hex()}
            if a.struct and os.path.isfile(struct):
                payload["struct_hex"] = open(struct, "rb").read().hex()
            up = post_json_big("/api/prim/reload", payload)
            if up.get("ok"):
                d2 = up.get("data") or {}
                res["prim"] = {"synced": True, "via": "upload", "xml": xml,
                               "struct": payload.get("struct_hex") is not None and struct,
                               "stored": up.get("stored"), "warning": up.get("warning"),
                               "count": d2.get("count"), "sections": d2.get("sections")}
            else:
                # 回落：让服务按路径热加载（服务需能读到该路径）
                rl = http_json("POST", "/api/prim/reload", {"path": to_win_path(xml)})
                d2 = (rl.get("data") or {})
                res["prim"] = {"synced": bool(rl.get("ok")), "via": "reload_path",
                               "xml": xml, "count": d2.get("count"),
                               "sections": d2.get("sections"),
                               "upload_error": up.get("error"),
                               "error": None if rl.get("ok") else rl.get("error")}

    # ---- 8 激活核对 ----
    res["step"] = "verify"
    v = run_ctl("version", timeout=30)
    res["after"]["module_ver_fresh"] = (v.get("data") or {}).get("module_ver")
    same = res["after"]["module_ver_fresh"] == res["before"]["module_ver"]
    res["activation"] = {
        "reconnected": reconnected,
        "version_string_same": same,
        "note": ("版本串为编译期常量，同串不代表没换镜像；"
                 "以回连 + 业务日志/探针为准" if same else "版本串已变化"),
    }

    res.update(ok=True, step="done", finished_at=now(),
               elapsed_s=round(time.time() - t_start, 1))
    emit(res, a.json_out)
    sys.exit(0)


def emit(res, json_out):
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    print(txt)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            f.write(txt + "\n")


if __name__ == "__main__":
    main()
