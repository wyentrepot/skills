#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fcctl.py — 海思 DW31 诊断上位机 CLI（WSL 侧 AI 控制入口）
==========================================================
双后端：
  new    = Windows FC Agent 网关 127.0.0.1:8770（protocol.md v1 信封）
  legacy = Windows fc_service.py 127.0.0.1:8765（现网可用、扁平 JSON）

默认 auto：优先选“设备链路就绪”的后端；8770 的 wsl.state=down 时自动回退 8765。

硬规则：
  - 烧录提交（flash-commit）必须在用户对话明确允许后调用，且必须带
    --approval-id + --user-approval（服务端再校验 human_confirmed/包 SHA）。
  - 不暴露旧版 /api/upg/load、/api/upg/start。
  - nv-write 必须显式 --confirm。
  - 所有输出为单行/缩进 JSON，便于 AI 读取。

用法示例：
  python3 tools/fcctl.py doctor
  python3 tools/fcctl.py status
  python3 tools/fcctl.py version
  python3 tools/fcctl.py frames --limit 5
  python3 tools/fcctl.py prim --limit 5
  python3 tools/fcctl.py topo
  python3 tools/fcctl.py nv-read 1025
  python3 tools/fcctl.py send --cmd 0x3013
  python3 tools/fcctl.py flash-prepare /mnt/c/.../x.hupg
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import select
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_NEW_BASE = "http://127.0.0.1:8770"
DEFAULT_LEGACY_BASE = "http://127.0.0.1:8765"
DEFAULT_HTTP_TIMEOUT = 10.0
PROBE_TIMEOUT = 3.0
LOG_CMDS = {0x5304, 0x5314, 0x5315, 0x5316}
TRANSPORT = os.environ.get("FC_DW31_TRANSPORT", "auto").lower()
WIN_CURL_CANDIDATES = (
    "/mnt/c/Windows/System32/curl.exe",
    "/mnt/c/Windows/system32/curl.exe",
)

EXIT_OK = 0
EXIT_BACKEND = 1
EXIT_USAGE = 2
EXIT_UNREACHABLE = 3
EXIT_DEVICE = 4

_DEVICE_CODES = {
    "NOT_LOGGED_IN", "SESSION_MUTED", "COM_RELEASED",
    "FLASH_NOT_PREPARED", "FLASH_APPROVAL_EXPIRED",
}
_UNREACHABLE_CODES = {
    "WSL_DOWN", "WSL_TIMEOUT", "UPSTREAM_ERROR", "UNREACHABLE",
    "NO_BACKEND", "NEW_BACKEND_UNAVAILABLE", "LEGACY_BACKEND_UNAVAILABLE",
}


class FcError(Exception):
    def __init__(self, code, message, detail=None, http_status=None, exit_code=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.http_status = http_status
        if exit_code is None:
            if code in _UNREACHABLE_CODES:
                exit_code = EXIT_UNREACHABLE
            elif code in _DEVICE_CODES:
                exit_code = EXIT_DEVICE
            else:
                exit_code = EXIT_BACKEND
        self.exit_code = exit_code

    def to_dict(self):
        err = {"code": self.code, "message": self.message}
        if self.detail is not None:
            err["detail"] = self.detail
        if self.http_status is not None:
            err["http_status"] = self.http_status
        return err


class Unreachable(FcError):
    def __init__(self, code, message, detail=None):
        super().__init__(code, message, detail, exit_code=EXIT_UNREACHABLE)


class BadRequest(FcError):
    def __init__(self, code, message, detail=None):
        super().__init__(code, message, detail, exit_code=EXIT_USAGE)


# ============================== HTTP ==============================

def _in_wsl():
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    return "microsoft" in platform.release().lower()


def _win_curl_path():
    for path in WIN_CURL_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _http_direct(method, url, body=None, timeout=DEFAULT_HTTP_TIMEOUT, headers=None):
    data = None
    hdrs = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        raise Unreachable("UNREACHABLE", f"{method} {url} 不可达: {e}",
                          {"url": url})


def _http_win_curl(method, url, body=None, timeout=DEFAULT_HTTP_TIMEOUT):
    """在 WSL 里通过 Windows curl.exe 访问 Windows 回环服务。"""
    exe = _win_curl_path()
    if not exe:
        raise Unreachable("WIN_CURL_MISSING",
                          "未找到 Windows curl.exe；无法访问 Windows 回环服务",
                          {"url": url})
    max_time = max(1, int(round(float(timeout))))
    cmd = [exe, "-sS", "--connect-timeout", "1", "--max-time", str(max_time),
           "-X", method,
           "-H", "Accept: application/json",
           "-w", "\n__FC_HTTP_STATUS__:%{http_code}", url]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json",
                "--data-binary", json.dumps(body, ensure_ascii=False)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=max_time + 5)
    except (subprocess.TimeoutExpired, OSError) as e:
        raise Unreachable("UNREACHABLE", f"Windows curl 调用失败: {e}",
                          {"url": url, "transport": "wincurl"})
    out = proc.stdout.decode("utf-8", "replace")
    marker = "\n__FC_HTTP_STATUS__:"
    idx = out.rfind(marker)
    status = 0
    if idx >= 0:
        text = out[:idx]
        try:
            status = int(out[idx + len(marker):].strip().splitlines()[0])
        except (ValueError, IndexError):
            status = 0
    else:
        text = out
    if proc.returncode != 0 and status == 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise Unreachable("UNREACHABLE",
                          f"Windows curl 失败: {err or proc.returncode}",
                          {"url": url, "transport": "wincurl"})
    return status, text.encode("utf-8")


def _http(method, url, body=None, timeout=DEFAULT_HTTP_TIMEOUT, headers=None):
    mode = TRANSPORT
    if mode == "wincurl":
        return _http_win_curl(method, url, body=body, timeout=timeout)
    if mode == "direct":
        return _http_direct(method, url, body=body, timeout=timeout, headers=headers)
    # auto：先直连；只有“连接被拒绝”才切 Windows curl（避免 POST 超时重放）
    try:
        return _http_direct(method, url, body=body, timeout=timeout, headers=headers)
    except Unreachable as e:
        text = str(e)
        refused = ("Connection refused" in text or "Errno 111" in text
                   or "拒绝" in text)
        if refused and _in_wsl() and _win_curl_path():
            return _http_win_curl(method, url, body=body, timeout=timeout)
        raise


def _json_http(method, url, body=None, timeout=DEFAULT_HTTP_TIMEOUT):
    status, raw = _http(method, url, body=body, timeout=timeout)
    text = raw.decode("utf-8", "replace")
    if not text.strip():
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        raise FcError("BAD_RESPONSE", f"非 JSON 响应 (HTTP {status})",
                      {"body": text[:800]}, http_status=status)


def _q(value):
    return urllib.parse.quote(str(value), safe="")


def _port_open_locally(url):
    parsed = urllib.parse.urlparse(url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 80),
                                      timeout=0.35):
            return True
    except OSError:
        return False


def _read_sse(url, seconds):
    """读取 SSE；WSL 下若本地端口不通，自动改用 Windows curl.exe 流式读取。"""
    events = []
    state = {"event": "message", "data": []}

    def feed(raw_line):
        text = raw_line.decode("utf-8", "replace").rstrip("\r\n")
        if text.startswith("event:"):
            state["event"] = text[6:].strip()
        elif text.startswith("data:"):
            state["data"].append(text[5:].strip())
        elif text == "":
            if state["data"]:
                events.append({"event": state["event"],
                               "data": "\n".join(state["data"])})
            state["event"], state["data"] = "message", []

    use_win = (TRANSPORT == "wincurl"
               or (TRANSPORT == "auto" and _in_wsl() and _win_curl_path()
                   and not _port_open_locally(url)))
    if use_win:
        exe = _win_curl_path()
        if not exe:
            raise Unreachable("WIN_CURL_MISSING", "未找到 Windows curl.exe",
                              {"url": url})
        cmd = [exe, "-sS", "-N", "--connect-timeout", "1", "--max-time",
               str(max(2, int(round(seconds)) + 5)),
               "-H", "Accept: text/event-stream", url]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + seconds
            while time.time() < deadline:
                remain = max(0.01, min(1.0, deadline - time.time()))
                ready, _, _ = select.select([proc.stdout], [], [], remain)
                if not ready:
                    continue
                line = proc.stdout.readline()
                if not line:
                    break
                feed(line)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    else:
        req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        try:
            with urllib.request.urlopen(
                    req, timeout=max(2.0, min(5.0, seconds + 2))) as resp:
                deadline = time.time() + seconds
                while time.time() < deadline:
                    line = resp.readline()
                    if not line:
                        break
                    feed(line)
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
            raise Unreachable("SSE_UNREACHABLE", f"SSE 读取失败: {e}",
                              {"url": url})
    if state["data"]:
        events.append({"event": state["event"], "data": "\n".join(state["data"])})
    return events


# ============================== Backends ==============================

class NewBackend:
    """Windows FC Agent 网关 8770：{"ok":true,"data":...} / {"ok":false,"error":...}"""
    name = "new"

    def __init__(self, base, timeout=DEFAULT_HTTP_TIMEOUT):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def call(self, method, path, body=None, timeout=None):
        status, obj = _json_http(method, self.base + path, body=body,
                                 timeout=timeout or self.timeout)
        if isinstance(obj, dict) and obj.get("ok") is False:
            err = obj.get("error")
            if not isinstance(err, dict):
                err = {"message": str(err)}
            code = err.get("code") or "UPSTREAM_ERROR"
            if code in _DEVICE_CODES and status in (409, 503):
                pass
            raise FcError(code, err.get("message") or "上游返回失败",
                          err.get("detail"), http_status=status)
        if status >= 400:
            raise FcError("HTTP_%d" % status, f"HTTP {status}",
                          obj if isinstance(obj, (dict, list)) else str(obj),
                          http_status=status)
        if isinstance(obj, dict) and "data" in obj:
            return obj["data"]
        return obj


class LegacyBackend:
    """fc_service.py 8765：扁平 JSON，失败时 {"ok":false,"error":...}"""
    name = "legacy"

    def __init__(self, base, timeout=DEFAULT_HTTP_TIMEOUT):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def call(self, method, path, body=None, timeout=None):
        status, obj = _json_http(method, self.base + path, body=body,
                                 timeout=timeout or self.timeout)
        if isinstance(obj, dict) and obj.get("ok") is False:
            err = obj.get("error")
            msg = err.get("message") if isinstance(err, dict) else str(err)
            code = err.get("code") if isinstance(err, dict) else None
            if not code:
                if "未登录" in (msg or ""):
                    code = "NOT_LOGGED_IN"
                elif "端口未打开" in (msg or "") or "已让出" in (msg or ""):
                    code = "COM_RELEASED"
                else:
                    code = "LEGACY_ERROR"
            raise FcError(code, msg or "旧版服务返回失败", obj,
                          http_status=status)
        if status >= 400:
            raise FcError("HTTP_%d" % status, f"HTTP {status}",
                          obj if isinstance(obj, (dict, list)) else str(obj),
                          http_status=status)
        return obj


def _new_probe(base, timeout=PROBE_TIMEOUT):
    out = {"reachable": False, "base": base, "device_ready": False}
    try:
        st, health = _json_http("GET", base + "/health", timeout=timeout)
        out["health_http"] = st
        out["health"] = health
        if st >= 400:
            raise FcError("HTTP_%d" % st, f"/health HTTP {st}", health, http_status=st)
        out["reachable"] = True
        try:
            st2, status_obj = _json_http("GET", base + "/api/v1/status", timeout=timeout)
            out["status_http"] = st2
            out["status"] = status_obj
            data = status_obj.get("data") if isinstance(status_obj, dict) else None
            if not isinstance(data, dict):
                data = {}
            wsl = data.get("wsl") or {}
            session = data.get("session")
            out["wsl_state"] = wsl.get("state")
            out["session"] = session
            out["device_ready"] = (wsl.get("state") == "up" and session is not None)
            if out["device_ready"]:
                out["reason"] = "wsl.state=up 且 session 非空"
            elif wsl.get("state") != "up":
                out["reason"] = f"wsl.state={wsl.get('state')!r}，WSL Agent 8780 未就绪"
            else:
                out["reason"] = "session 为 null（WSL /api/v1/status 超时或无数据）"
        except FcError as e:
            out["status_error"] = e.to_dict()
            out["reason"] = f"/health 可达，但 /api/v1/status 失败: {e.message}"
    except FcError as e:
        out["error"] = e.to_dict()
        out["reason"] = e.message
    return out


def _legacy_probe(base, timeout=PROBE_TIMEOUT):
    out = {"reachable": False, "base": base, "device_ready": False}
    try:
        st, state = _json_http("GET", base + "/api/state", timeout=timeout)
        out["state_http"] = st
        if st >= 400:
            raise FcError("HTTP_%d" % st, f"/api/state HTTP {st}", state, http_status=st)
        out["reachable"] = True
        out["state"] = state
        state = state if isinstance(state, dict) else {}
        out["port_open"] = bool(state.get("port_open"))
        out["logged_in"] = bool(state.get("logged_in"))
        out["start_running"] = bool(state.get("start_running"))
        out["mode"] = state.get("mode")
        out["device_ready"] = (out["port_open"] and out["logged_in"]
                               and not out["start_running"])
        if out["device_ready"]:
            out["reason"] = "port_open=true 且 logged_in=true"
        elif out["start_running"]:
            out["reason"] = "Start.exe 运行中，端口已让出"
        elif not out["port_open"]:
            out["reason"] = "port_open=false（端口未打开/已让出）"
        else:
            out["reason"] = "logged_in=false（未登录）"
    except FcError as e:
        out["error"] = e.to_dict()
        out["reason"] = e.message
    return out


def _bases(args):
    new_base = (getattr(args, "new_base", None)
                or os.environ.get("FC_DW31_NEW_BASE") or DEFAULT_NEW_BASE)
    legacy_base = (getattr(args, "legacy_base", None)
                   or os.environ.get("FC_DW31_LEGACY_BASE") or DEFAULT_LEGACY_BASE)
    return new_base, legacy_base


def _http_timeout(args):
    return float(getattr(args, "http_timeout", None) or DEFAULT_HTTP_TIMEOUT)


def _select(args, need="device"):
    """返回 (backend, info)。info 含 selected/selected_reason/probes。"""
    mode = (getattr(args, "backend", None)
            or os.environ.get("FC_DW31_BACKEND") or "auto").lower()
    new_base, legacy_base = _bases(args)
    timeout = _http_timeout(args)

    if mode == "new":
        if need == "legacy":
            raise BadRequest("BACKEND_UNSUPPORTED",
                             "该命令仅 8765 旧版支持；当前显式指定 --backend new")
        return NewBackend(new_base, timeout), {
            "selected": "new", "selected_reason": "显式指定 --backend new",
            "new_base": new_base, "legacy_base": legacy_base,
        }
    if mode == "legacy":
        if need == "new":
            raise BadRequest("BACKEND_UNSUPPORTED",
                             "该命令仅 8770 新协议支持；当前显式指定 --backend legacy")
        return LegacyBackend(legacy_base, timeout), {
            "selected": "legacy", "selected_reason": "显式指定 --backend legacy",
            "new_base": new_base, "legacy_base": legacy_base,
        }

    n = _new_probe(new_base)
    l = _legacy_probe(legacy_base)

    if need == "new":
        if n["reachable"]:
            return NewBackend(new_base, timeout), {
                "selected": "new", "selected_reason": "8770 可达（命令仅新协议支持）",
                "probes": {"new": n, "legacy": l},
            }
        raise Unreachable("NEW_BACKEND_UNAVAILABLE",
                          "8770 新网关不可达；该命令仅新协议支持",
                          {"new": n, "legacy": l})
    if need == "legacy":
        if l["reachable"]:
            return LegacyBackend(legacy_base, timeout), {
                "selected": "legacy", "selected_reason": "8765 可达（命令仅旧版支持）",
                "probes": {"new": n, "legacy": l},
            }
        raise Unreachable("LEGACY_BACKEND_UNAVAILABLE",
                          "8765 旧版服务不可达；该命令仅旧版支持",
                          {"new": n, "legacy": l})

    if n["reachable"] and n["device_ready"]:
        return NewBackend(new_base, timeout), {
            "selected": "new", "selected_reason": "8770 设备链路就绪",
            "probes": {"new": n, "legacy": l},
        }
    if l["reachable"] and l["device_ready"]:
        extra = ""
        if n["reachable"]:
            extra = f"；8770 设备链路不可用（{n.get('reason')}）"
        return LegacyBackend(legacy_base, timeout), {
            "selected": "legacy",
            "selected_reason": "8765 设备就绪" + extra,
            "probes": {"new": n, "legacy": l},
        }
    if l["reachable"]:
        return LegacyBackend(legacy_base, timeout), {
            "selected": "legacy",
            "selected_reason": f"8765 可达但设备未就绪（{l.get('reason')}），命令可能失败",
            "probes": {"new": n, "legacy": l},
        }
    if n["reachable"]:
        return NewBackend(new_base, timeout), {
            "selected": "new",
            "selected_reason": f"仅 8770 可达且设备未就绪（{n.get('reason')}），设备命令可能 503",
            "probes": {"new": n, "legacy": l},
        }
    raise Unreachable("NO_BACKEND", "8770 与 8765 均不可达",
                      {"new": n, "legacy": l})


# ============================== Output ==============================

def _emit(args, ok, backend=None, base=None, reason=None, data=None,
          error=None, exit_code=None):
    out = {"ok": ok, "transport": TRANSPORT}
    if backend:
        out["backend"] = backend
    if base:
        out["base"] = base
    if reason:
        out["selected_reason"] = reason
    if ok:
        out["data"] = data
    else:
        out["error"] = error
    print(json.dumps(out, ensure_ascii=False,
                     indent=2 if getattr(args, "pretty", False) else None))
    return EXIT_OK if ok else (exit_code if exit_code is not None else EXIT_BACKEND)


def _ok(args, backend, info, data):
    return _emit(args, True, backend=backend.name, base=backend.base,
                 reason=info.get("selected_reason"), data=data)


# ============================== Helpers ==============================

def _int(value, name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise BadRequest("BAD_ARGUMENT", f"{name} 必须是整数: {value!r}")


def _cmd_id(value):
    text = str(value).strip()
    try:
        return int(text, 0) if text.lower().startswith("0x") else int(text, 10)
    except ValueError:
        raise BadRequest("BAD_ARGUMENT", f"cmd_id 非法: {value!r}（示例 0x3013）")


def _hex(value, name="hex"):
    text = str(value or "").replace(" ", "").replace("\n", "").replace("\t", "")
    if text.lower().startswith("0x"):
        text = text[2:]
    if len(text) % 2:
        raise BadRequest("BAD_ARGUMENT", f"{name} 长度必须为偶数: {len(text)}")
    try:
        bytes.fromhex(text)
    except ValueError:
        raise BadRequest("BAD_ARGUMENT", f"{name} 含非十六进制字符")
    return text.lower()


def _clamp(value, low, high):
    return max(low, min(high, value))


UPG_STATUS_TEXT = {
    0x00: "OK",
    0x01: "END(验证中)",
    0xF0: "PROCESS",
    0xF1: "TRANSMIT",
    0xFF: "FAIL",
}


def _parse_upg_3410(param_hex):
    """解析 0x3410 的 60B 应答（ext_upg_status_ind_s，ver0 截断布局）。

    偏移以 references/contract.md §3.4 为准：
      +0 u32 upg_id      +4 u32 blk_size(300)  +8 u32 file_size
      +12 u32 num        +16 u16 last_blk_idx  +18 u16 error_code
      +20 u32 rcv_file_size  +24 u8 upg_status
    ⚠ 不要按旧布局（ext_upg_status_ind_entire）读：那会把偏移 20 的
      rcv_file_size 低字节当成 upg_status（实测把 0x10 报成 STOPPING/UNKNOWN）。
    """
    text = str(param_hex or "").strip()
    try:
        p = bytes.fromhex(text)
    except ValueError:
        return {"raw_hex": text, "error": "param_hex 非十六进制"}
    out = {"raw_hex": text, "size": len(p)}
    if len(p) < 28:
        out["error"] = f"0x3410 应答长度 {len(p)} < 28（无法解析状态）"
        return out
    status = p[24]
    out.update({
        "upg_id": int.from_bytes(p[0:4], "little"),
        "blk_size": int.from_bytes(p[4:8], "little"),
        "file_size": int.from_bytes(p[8:12], "little"),
        "num": int.from_bytes(p[12:16], "little"),
        "last_blk_idx": int.from_bytes(p[16:18], "little"),
        "error_code": int.from_bytes(p[18:20], "little"),
        "rcv_file_size": int.from_bytes(p[20:24], "little"),
        "upg_status": status,
        "upg_status_text": UPG_STATUS_TEXT.get(status, f"UNKNOWN(0x{status:02X})"),
    })
    if len(p) >= 60:
        out["mac"] = ":".join(f"{b:02X}" for b in p[50:56])
        out["upg_end_time"] = int.from_bytes(p[56:60], "little")
    return out


def _flash_summary(data):
    """把 8765 /api/upg/progress 与 8770 /upgrade/status 归一成易读摘要。"""
    if not isinstance(data, dict):
        return None
    progress = data.get("progress") or {}
    module = data.get("module") or {}
    package = data.get("package") or {}
    sent = progress.get("sent", data.get("sent", 0)) or 0
    total = progress.get("total", data.get("total", 0)) or 0
    percent = progress.get("percent")
    size = package.get("size") or data.get("size") or 0
    rcv = module.get("rcv_file_size")
    if (percent is None or percent == 0) and total:
        percent = round(float(sent) * 100.0 / float(total), 1)
    if (percent is None or percent == 0) and size and rcv:
        percent = round(float(rcv) * 100.0 / float(size), 1)
        if percent > 100.0:
            percent = 100.0
    reboot = data.get("reboot") or {}
    activation = data.get("activation") or {}
    return {
        "state": data.get("state"),
        "approval_id": data.get("approval_id"),
        "package_sha256": package.get("sha256"),
        "package_size": size or None,
        "percent": percent,
        "sent": sent,
        "total": total,
        "last_blk": progress.get("last_blk"),
        "rcv_file_size": rcv,
        "upg_status": module.get("upg_status"),
        "upg_status_text": module.get("upg_status_text"),
        "error_code": module.get("error_code"),
        "error": data.get("error"),
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "version_after": data.get("version_after"),
        # 激活层判据（DONE 不等于切镜像，见 contract.md §4）
        "reconnect_ok": reboot.get("reconnect_ok"),
        "reset_interval": reboot.get("reset_interval"),
        "activation_confirmed": activation.get("confirmed"),
        "version_before": activation.get("version_before"),
        "target_version": activation.get("target_version"),
    }


def _as_int(value, default=-1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ============================== Commands ==============================

def cmd_doctor(args):
    new_base, legacy_base = _bases(args)
    n = _new_probe(new_base)
    l = _legacy_probe(legacy_base)
    data = {"new": n, "legacy": l}
    if n["reachable"] and n["device_ready"]:
        data["selected"] = "new"
        data["selected_reason"] = "8770 设备链路就绪"
        ok = True
    elif l["reachable"] and l["device_ready"]:
        data["selected"] = "legacy"
        data["selected_reason"] = (
            "8765 设备就绪" + (f"；8770 设备链路不可用（{n.get('reason')}）"
                               if n["reachable"] else "；8770 不可达"))
        ok = True
    elif l["reachable"]:
        data["selected"] = "legacy"
        data["selected_reason"] = f"8765 可达但设备未就绪（{l.get('reason')}）"
        ok = True
    elif n["reachable"]:
        data["selected"] = "new"
        data["selected_reason"] = f"仅 8770 可达且设备未就绪（{n.get('reason')}）"
        ok = True
    else:
        data["selected"] = None
        data["selected_reason"] = "8770 与 8765 均不可达"
        return _emit(args, False, reason=data["selected_reason"],
                     error={"code": "NO_BACKEND", "message": "8770 与 8765 均不可达",
                            "detail": data},
                     exit_code=EXIT_UNREACHABLE)
    return _emit(args, ok, backend=data["selected"],
                 base=new_base if data["selected"] == "new" else legacy_base,
                 reason=data["selected_reason"], data=data)


def cmd_status(args):
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", "/api/v1/status")
    else:
        data = backend.call("GET", "/api/state")
    return _ok(args, backend, info, data)


def cmd_version(args):
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", "/api/v1/session")
    else:
        data = backend.call("GET", "/api/version")
    return _ok(args, backend, info, data)


def cmd_frames(args):
    since = _int(args.since, "since")
    limit = _clamp(_int(args.limit, "limit"), 1, 2000)
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", f"/api/v1/frames?since={since}&limit={limit}")
    else:
        data = backend.call("GET", f"/api/frames?since={since}&limit={limit}")
    return _ok(args, backend, info, data)


def cmd_logs(args):
    since = _int(args.since, "since")
    limit = _clamp(_int(args.limit, "limit"), 1, 2000)
    backend, info = _select(args, "device")
    if backend.name == "new":
        fetch = _clamp(limit * 4, limit, 2000)
        data = backend.call("GET", f"/api/v1/frames?since={since}&limit={fetch}")
        frames = [f for f in (data.get("frames") or [])
                  if _as_int(f.get("cmd_id")) in LOG_CMDS]
        data = {"frames": frames[:limit], "count": len(frames[:limit]),
                "last_id": max([int(f.get("id", 0)) for f in frames] or [since])}
    else:
        data = backend.call("GET", f"/api/logs?since={since}&limit={limit}")
    return _ok(args, backend, info, data)


def cmd_prim(args):
    since = _int(args.since, "since")
    limit = _clamp(_int(args.limit, "limit"), 1, 2000)
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", f"/api/v1/prim/messages?since={since}&limit={limit}")
    else:
        data = backend.call("GET", f"/api/prim/logs?since={since}&limit={limit}")
    return _ok(args, backend, info, data)


def cmd_prim_frame(args):
    fid = _int(args.id, "id")
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", f"/api/v1/prim/frame/{fid}")
    else:
        data = backend.call("GET", f"/api/prim/frame?id={fid}")
    return _ok(args, backend, info, data)


def cmd_topo(args):
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", "/api/v1/topology", timeout=args.timeout + 5)
    else:
        data = backend.call("GET", f"/api/dev/topo?timeout={args.timeout}",
                            timeout=args.timeout + 5)
    return _ok(args, backend, info, data)


def cmd_nv_list(args):
    params = []
    if args.module:
        params.append("module=" + _q(args.module))
    if args.q:
        params.append("q=" + _q(args.q))
    if args.cco:
        params.append("cco=1")
    params.append("limit=%d" % _clamp(int(args.limit), 1, 1000))
    query = "?" + "&".join(params)
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", "/api/v1/nv/items" + query)
    else:
        data = backend.call("GET", "/api/nv/items" + query)
    return _ok(args, backend, info, data)


def cmd_nv_read(args):
    nv_id = _int(args.nv_id, "nv_id")
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", f"/api/v1/nv/read?nv_id={nv_id}")
    else:
        data = backend.call("POST", "/api/nv/read",
                            {"nv_id": nv_id, "wait": args.wait}, timeout=args.wait + 8)
    return _ok(args, backend, info, data)


def cmd_nv_write(args):
    if not args.confirm:
        raise BadRequest("CONFIRM_REQUIRED",
                         "NV 写是设备写操作；确认后加 --confirm 再执行")
    nv_id = _int(args.nv_id, "nv_id")
    data_hex = _hex(args.hex, "data_hex")
    backend, info = _select(args, "device")
    body = {"nv_id": nv_id, "data_hex": data_hex, "verify": not args.no_verify}
    if backend.name == "new":
        data = backend.call("POST", "/api/v1/nv/write", body, timeout=args.wait + 10)
    else:
        body["confirm"] = True
        data = backend.call("POST", "/api/nv/write", body, timeout=args.wait + 10)
    return _ok(args, backend, info, data)


def cmd_send(args):
    cmd_id = _cmd_id(args.cmd)
    param_hex = _hex(args.param_hex or "", "param_hex")
    body = {"cmd_id": cmd_id, "param_hex": param_hex,
            "secure": not args.plain, "wait": args.wait}
    backend, info = _select(args, "device")
    if backend.name == "new":
        body["cmd_id"] = hex(cmd_id)
        data = backend.call("POST", "/api/v1/raw/send", body, timeout=args.wait + 8)
    else:
        data = backend.call("POST", "/api/send", body, timeout=args.wait + 8)
    return _ok(args, backend, info, data)


def cmd_mode(args):
    backend, info = _select(args, "legacy")
    data = backend.call("POST", "/api/mode", {"mode": args.mode})
    return _ok(args, backend, info, data)


def cmd_events(args):
    seconds = max(1.0, float(args.seconds))
    backend, info = _select(args, "device")
    events = []
    if backend.name == "new":
        events = _read_sse(backend.base + "/api/v1/events", seconds)
    else:
        baseline = backend.call("GET", "/api/logs?since=0&limit=200")
        last = max([_as_int(item.get("id"), 0)
                    for item in (baseline.get("logs") or [])] or [0])
        deadline = time.time() + seconds
        while time.time() < deadline:
            data = backend.call("GET", f"/api/logs?since={last}&limit=200")
            logs = data.get("logs") or []
            for item in logs:
                events.append(item)
                last = max(last, _as_int(item.get("id"), last))
            time.sleep(1.0)
    return _ok(args, backend, info, {"seconds": seconds, "count": len(events),
                                     "events": events})


def cmd_flash_prepare(args):
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("POST", "/api/v1/upgrade/prepare",
                            {"package_path": args.package}, timeout=60)
    else:
        try:
            data = backend.call("POST", "/api/upg/prepare",
                                {"package_path": args.package}, timeout=60)
        except FcError as e:
            if e.http_status == 404 or e.code in ("HTTP_404", "NOT_FOUND"):
                raise FcError(
                    "LEGACY_PREPARE_MISSING",
                    "8765 尚未实现 /api/upg/prepare（旧版服务）；"
                    "请升级 Windows 侧服务，不要退回 /api/upg/load 或 /api/upg/start",
                    {"http_status": e.http_status}, exit_code=EXIT_BACKEND)
            raise
    return _ok(args, backend, info, data)


def cmd_flash_status(args):
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("GET", "/api/v1/upgrade/status")
    else:
        data = backend.call("GET", "/api/upg/progress")
    summary = _flash_summary(data)
    if summary is not None:
        data = {"summary": summary, "raw": data}
    return _ok(args, backend, info, data)


def cmd_flash_module_status(args):
    backend, info = _select(args, "device")
    body = {"cmd_id": 0x3410, "param_hex": "00000000",
            "secure": not args.plain, "wait": args.wait}
    if backend.name == "new":
        body["cmd_id"] = "0x3410"
        resp = backend.call("POST", "/api/v1/raw/send", body,
                            timeout=args.wait + 8)
    else:
        resp = backend.call("POST", "/api/send", body, timeout=args.wait + 8)
    ack = (resp or {}).get("ack") or {}
    module = _parse_upg_3410(ack.get("param_hex"))
    return _ok(args, backend, info, {
        "ack": ack,
        "module": module,
        "note": "0x3410 的 param 固定 4B 00000000；进度看 module.rcv_file_size",
    })


def cmd_flash_stop(args):
    backend, info = _select(args, "device")
    if backend.name == "new":
        data = backend.call("POST", "/api/v1/upgrade/stop", {}, timeout=15)
    else:
        if not args.force:
            raise BadRequest(
                "LEGACY_STOP_NEEDS_FORCE",
                "8765 停止烧录需显式 --force（防止误停；停止是安全动作，但必须由人要求）")
        data = backend.call("POST", "/api/upg/stop", {}, timeout=15)
    return _ok(args, backend, info, data)


def cmd_flash_commit(args):
    """提交烧录（对话级授权）。

    服务端仍会校验 human_confirmed/approval_id/包 SHA；本命令额外要求
    --user-approval（用户明确允许的原话/摘要），没有就不发请求。
    """
    backend, info = _select(args, "device")
    approval = (args.approval_id or "").strip()
    if not approval:
        raise BadRequest("APPROVAL_REQUIRED",
                         "commit 必须带 --approval-id（先 flash-prepare 取 approval_id）")
    user_approval = (args.user_approval or "").strip()
    if not user_approval:
        raise BadRequest(
            "USER_APPROVAL_REQUIRED",
            "commit 必须带 --user-approval（用户明确允许的原话/摘要）；"
            "用户没有明确说「允许 / 可以烧」时不要调用本命令")
    body = {"approval_id": approval, "human_confirmed": True,
            "approved_by": args.approved_by, "user_approval": user_approval}
    if args.reset_interval is not None:
        body["reset_interval"] = _clamp(int(args.reset_interval), 0, 3600)
    if args.option is not None:
        body["option"] = int(str(args.option), 0)
    if backend.name == "new":
        data = backend.call("POST", "/api/v1/upgrade/commit", body, timeout=30)
    else:
        data = backend.call("POST", "/api/upg/commit", body, timeout=30)
    return _ok(args, backend, info, data)


def cmd_flash_reboot(args):
    """发送 0x3419 让模块复位（仅 8765）。不传 upg_id 时服务沿用最近一次升级 ID。"""
    backend, info = _select(args, "legacy")
    body = {"dry_run": bool(args.dry_run)}
    if args.reset_interval is not None:
        body["reset_interval"] = _clamp(int(args.reset_interval), 0, 3600)
    if args.upg_id is not None:
        body["upg_id"] = int(str(args.upg_id), 0)
    if args.option is not None:
        body["option"] = int(str(args.option), 0)
    data = backend.call("POST", "/api/upg/reboot", body, timeout=20)
    return _ok(args, backend, info, data)


def cmd_build_start(args):
    backend, info = _select(args, "new")
    data = backend.call("POST", "/api/v1/build/start", {"target": args.target}, timeout=15)
    return _ok(args, backend, info, data)


def cmd_build_status(args):
    backend, info = _select(args, "new")
    data = backend.call("GET", "/api/v1/build/status")
    return _ok(args, backend, info, data)


def cmd_build_log(args):
    since = _int(args.since, "since")
    backend, info = _select(args, "new")
    data = backend.call("GET", f"/api/v1/build/log?since={since}")
    return _ok(args, backend, info, data)


# ============================== Parser ==============================

def _add_common(p, suppress=False):
    d = argparse.SUPPRESS if suppress else None
    p.add_argument("--backend", choices=["auto", "new", "legacy"], default=d,
                   help="auto（默认）| new=8770 | legacy=8765")
    p.add_argument("--new-base", default=d, help="8770 基地址")
    p.add_argument("--legacy-base", default=d, help="8765 基地址")
    p.add_argument("--http-timeout", type=float, default=d, help="HTTP 超时秒数")
    p.add_argument("--transport", choices=["auto", "direct", "wincurl"], default=d,
                   help="auto（默认）| direct | wincurl（WSL 经 Windows curl.exe）")
    p.add_argument("--pretty", action="store_true", default=d, help="缩进输出")


def build_parser():
    p = argparse.ArgumentParser(
        prog="fcctl.py",
        description="海思 DW31 诊断上位机 CLI（WSL 侧 AI 控制入口）",
        epilog="commit 走 flash-commit：必须带 --approval-id 与 --user-approval；用户未明确允许时禁止调用。")
    _add_common(p)
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, func, help_text, **kwargs):
        sp = sub.add_parser(name, help=help_text, **kwargs)
        sp.set_defaults(func=func)
        _add_common(sp, suppress=True)
        return sp

    add("doctor", cmd_doctor, "探测 8770/8765，报告选中的后端")
    add("status", cmd_status, "状态（8770 聚合状态 / 8765 /api/state）")
    add("version", cmd_version, "模块版本（8770 /session / 8765 /api/version）")

    sp = add("frames", cmd_frames, "原始帧（增量）")
    sp.add_argument("--since", type=int, default=0)
    sp.add_argument("--limit", type=int, default=50)

    sp = add("logs", cmd_logs, "日志类帧（0x5304/5314/5315/5316）")
    sp.add_argument("--since", type=int, default=0)
    sp.add_argument("--limit", type=int, default=100)

    sp = add("prim", cmd_prim, "prim 消息（解析后的日志行）")
    sp.add_argument("--since", type=int, default=0)
    sp.add_argument("--limit", type=int, default=100)

    sp = add("prim-frame", cmd_prim_frame, "prim 结构树")
    sp.add_argument("--id", type=int, required=True)

    sp = add("topo", cmd_topo, "拓扑查询")
    sp.add_argument("--timeout", type=float, default=3.5,
                    help="设备查询超时秒数（默认 3.5）")

    sp = add("nv-list", cmd_nv_list, "NV 目录")
    sp.add_argument("--module", default="")
    sp.add_argument("--q", default="")
    sp.add_argument("--cco", action="store_true")
    sp.add_argument("--limit", type=int, default=300)

    sp = add("nv-read", cmd_nv_read, "NV 读")
    sp.add_argument("nv_id", type=int)
    sp.add_argument("--wait", type=float, default=2.2)

    sp = add("nv-write", cmd_nv_write, "NV 写（必须 --confirm）")
    sp.add_argument("nv_id", type=int)
    sp.add_argument("--hex", required=True, dest="hex")
    sp.add_argument("--no-verify", action="store_true")
    sp.add_argument("--confirm", action="store_true")
    sp.add_argument("--wait", type=float, default=3.0)

    sp = add("send", cmd_send, "发送原始诊断命令")
    sp.add_argument("--cmd", required=True, help="如 0x3013")
    sp.add_argument("--param-hex", default="")
    sp.add_argument("--plain", action="store_true", help="不加密（默认加密）")
    sp.add_argument("--wait", type=float, default=2.0)

    sp = add("mode", cmd_mode, "旧版端口仲裁 auto|ai|manual（仅 8765）")
    sp.add_argument("mode", choices=["auto", "ai", "manual"])

    sp = add("events", cmd_events, "事件（8770 SSE / 8765 轮询日志）")
    sp.add_argument("--seconds", type=float, default=10.0)

    sp = add("flash-prepare", cmd_flash_prepare,
             "烧录 prepare（只校验，不写 flash；8770/8765 均可）")
    sp.add_argument("package")

    add("flash-status", cmd_flash_status,
        "烧录状态（summary.percent/rcv_file_size/upg_status_text）")
    sp = add("flash-module-status", cmd_flash_module_status,
             "直接发 0x3410 查询模块升级状态（param 固定 4B 00000000）")
    sp.add_argument("--plain", action="store_true")
    sp.add_argument("--wait", type=float, default=2.0)
    sp = add("flash-stop", cmd_flash_stop, "中止烧录")
    sp.add_argument("--force", action="store_true", help="旧版 8765 才需要")
    sp = add("flash-commit", cmd_flash_commit,
             "提交烧录（对话级授权：必须 --approval-id + --user-approval）")
    sp.add_argument("--approval-id", required=True,
                    help="flash-prepare 返回的 approval_id")
    sp.add_argument("--user-approval", required=True,
                    help="用户明确允许的原话/摘要（如 允许）")
    sp.add_argument("--approved-by", default="cli",
                    choices=["cli", "mcp", "ai", "web"])
    sp.add_argument("--reset-interval", type=int, default=None,
                    help="0x3419 复位延时秒（0-3600，默认 3）")
    sp.add_argument("--option", default=None, help="0x3412 option（默认 0x22）")
    sp = add("flash-reboot", cmd_flash_reboot,
             "发 0x3419 复位模块（仅 8765；不传 upg_id 沿用最近升级 ID）")
    sp.add_argument("--reset-interval", type=int, default=None)
    sp.add_argument("--upg-id", default=None)
    sp.add_argument("--option", default=None)
    sp.add_argument("--dry-run", action="store_true",
                    help="只保存默认复位延时，不发 0x3419")

    sp = add("build-start", cmd_build_start, "启动构建（仅 8770）")
    sp.add_argument("target")
    add("build-status", cmd_build_status, "构建状态（仅 8770）")
    sp = add("build-log", cmd_build_log, "构建日志增量（仅 8770）")
    sp.add_argument("--since", type=int, default=0)

    return p


def main(argv=None):
    global TRANSPORT
    parser = build_parser()
    args = parser.parse_args(argv)
    TRANSPORT = (getattr(args, "transport", None)
                 or os.environ.get("FC_DW31_TRANSPORT") or "auto").lower()
    try:
        return args.func(args)
    except FcError as e:
        backend = None
        base = None
        # 尽力从异常 detail 中给出后端信息
        if isinstance(e.detail, dict):
            if "new" in e.detail and "legacy" in e.detail:
                backend = None
        return _emit(args, False, backend=backend, base=base,
                     error=e.to_dict(), exit_code=e.exit_code)
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass
        return EXIT_OK
    except KeyboardInterrupt:
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
