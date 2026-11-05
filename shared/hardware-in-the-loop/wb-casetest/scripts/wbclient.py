#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wbclient — 工作台(8790)最小 API 客户端,自动化测试框架的共享底座。

只做 HTTP 编排,不碰项目代码。约定:
- 本机 loopback + WORKBENCH_LOCAL_FULL_ACCESS=1 免 token,走 v2 门面(verification-runs)。
- simcon 串口物理独占:提交前先查 lease,409 时等待重试(不硬抢)。
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE = os.environ.get("WORKBENCH_BASE", "http://127.0.0.1:8790")


def _req(method, path, body=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"http_error": e.code, "detail": str(e)}
    except Exception as e:
        return {"http_error": -1, "detail": str(e)}


def get(path, timeout=30):
    return _req("GET", path, timeout=timeout)


def post(path, body=None, timeout=30):
    return _req("POST", path, body=body, timeout=timeout)


# ---------- simcon ----------

def lease():
    """simcon 闸门状态:{held:bool, holder:{...}}。提交前必查,409 不硬抢。"""
    return get("/api/ai/v2/simcon/lease")


def wait_lease_free(max_wait=300, poll=5):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        l = lease()
        if not l.get("held"):
            return True
        h = (l.get("holder") or {})
        print(f"[lease] 被占: {h.get('actor')} {h.get('kind')} elapsed={h.get('elapsed_seconds')}, 等 {poll}s")
        time.sleep(poll)
    return False


def build_frame(afn, fn, params=None, profile="anhui", seq=1, direction="down"):
    """语义构帧预检(不触串口)。返回 {"hex":...,"length":...} 或 422 detail。"""
    return post("/api/simcon/build", {
        "afn": afn, "fn": fn, "params": params or {},
        "direction": direction, "profile": profile, "seq": seq,
    })


def submit_v2_verify(steps, profile="anhui", mapping_id="simcon", client_request_id=None, **extra):
    """提交 v2 验证任务(异步 202)。steps 元素: {"name","send"/"recv_only"/"wait_mclt_stored"/"read_mclt_11e3","expect","expect_timeout"}"""
    body = {"task": dict({
        "mapping_id": mapping_id,
        "profile": profile,
        "steps": steps,
        "client_request_id": client_request_id or f"at-{int(time.time()*1000)}",
    }, **extra), "client_request_id": client_request_id or f"at-vr-{int(time.time()*1000)}"}
    return post("/api/ai/v2/verification-runs", body)


def poll_job(job_id, wait_seconds=30, max_poll=600):
    """轮询 v2 job 到终态。返回最终 job json。"""
    t0 = time.time()
    while time.time() - t0 < max_poll:
        j = get(f"/api/ai/v2/jobs/{job_id}?wait_seconds={wait_seconds}", timeout=wait_seconds + 30)
        state = j.get("job_state")
        if state in ("succeeded", "failed", "stopped"):
            return j
        time.sleep(2)
    return {"job_state": "timeout", "job_id": job_id}


def run_verify(steps, profile="anhui", mapping_id="simcon", poll_wait=20, max_poll=600, **extra):
    """一步到位:提交 + 轮询,返回归一化 {"ok","summary","steps","job_id"}。"""
    r = submit_v2_verify(steps, profile=profile, mapping_id=mapping_id, **extra)
    if "job_id" not in r:
        return {"ok": False, "error": r, "steps": []}
    j = poll_job(r["job_id"], wait_seconds=poll_wait, max_poll=max_poll)
    res = (j.get("result") or {}).get("result") or {}
    steps_res = res.get("steps") or []
    # step 元素的判定字段是 result:"pass"/"fail"(字符串),不是布尔 pass
    ok = j.get("job_state") == "succeeded" and (
        not steps_res or all(s.get("result") == "pass" for s in steps_res))
    under_err = ((j.get("result") or {}).get("error")) or ""
    return {"ok": bool(ok and j.get("job_state") == "succeeded"),
            "summary": j.get("summary"), "job_id": j.get("job_id"),
            "steps": steps_res, "run_id": res.get("run_id"),
            "frames_seq": res.get("frames_seq"), "underlying_error": under_err,
            "raw": j}


# ---------- simcon 帧日志 ----------

def frames(updown=None, afn=None, fn=None, direction=None, run_id=None,
           after_seq=None, limit=200, mapping="simcon"):
    q = f"limit={limit}"
    for k, v in (("updown", updown), ("afn", afn), ("fn", fn), ("direction", direction),
                 ("run_id", run_id), ("after_seq", after_seq)):
        if v is not None:
            q += f"&{k}={v}"
    return get(f"/api/ai/v1/simcon/frames?{q}") if mapping == "simcon" else {}


# ---------- simeter ----------

def simeter_open(mapping_id="listener"):
    return post("/api/simeter/open", {"mapping_id": mapping_id})


def simeter_close():
    return post("/api/simeter/close", {})


def simeter_status():
    return get("/api/simeter/status")


def simeter_frames(dir=None, after_seq=None, limit=200):
    q = f"limit={limit}"
    if dir:
        q += f"&dir={dir}"
    if after_seq is not None:
        q += f"&after_seq={after_seq}"
    return get(f"/api/simeter/frames?{q}")


def simeter_send_hex(hexstr):
    return post("/api/simeter/send_hex", {"hex": hexstr})


def simeter_oad(entries=None, reset=False):
    body = {"reset": True} if reset else {"entries": entries}
    return post("/api/simeter/oad", body)


def simeter_oad_get():
    return get("/api/simeter/oad")


def simeter_handle_hex(hexstr):
    return post("/api/simeter/handle_hex", {"hex": hexstr})


# ---------- F230 存数库 / 上报桶 ----------

def store_mclt(limit=20):
    return get(f"/api/simcon/store/mclt?limit={limit}")


def report_buckets():
    return get("/api/simcon/report_buckets")


def serial_bridge_status():
    return get("/api/serial-bridge/status")


if __name__ == "__main__":
    import sys
    print("health:", get("/api/health"))
    print("lease:", lease())
