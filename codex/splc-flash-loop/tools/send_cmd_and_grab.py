#!/usr/bin/env python3
"""
send_cmd_and_grab.py — 向板子串口发送命令并抓取关键字上下文.

通过 PowerShell 桥调用 Windows 侧 pyserial, 解决 WSL 无法直接访问 Windows COM 口的问题.
复用 EDBG 项目的 ``SerialBackend`` 类, 输出结构化 JSON.

用法 (WSL 中)::

    # 发命令 + 等关键字
    python3 send_cmd_and_grab.py --port COM23 --cmd "vermgmt bin" --keyword "[assoc]"
    python3 send_cmd_and_grab.py --port COM11 --cmd "version" --keyword "sversion"

    # 只收不发 (等效于 loop grab)
    python3 send_cmd_and_grab.py --port COM23 --keyword "sta main task" --timeout 120

    # 传 --type 自动按 /d/<type>/<project>/<timestamp>/ 格式生成证据路径
    python3 send_cmd_and_grab.py --port COM23 --cmd "vermgmt bin" --keyword "[assoc]" --type sta

输出 JSON::

    {
        "ok": true,
        "keyword": "[assoc]",
        "matched": true,
        "context": ["assoc_mode: 1(broadcast_auth), sta_auth:1", "[assoc] network_optimize:1"],
        "total_lines": 142,
        "evidence_path": "/d/sta/04-sta/20260729-094200/splc-COM23-20260729-094200"
    }

evidence_path 指向全量原始日志, AI 只处理 context.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROJECT_LABELS = {
    "sta": "04-sta",
    "cco": "001-cco",
}


def main():
    p = argparse.ArgumentParser(
        description="Send command to board serial and grab keyword context"
    )
    p.add_argument("--port", required=True, help="Windows COM port (e.g. COM23)")
    p.add_argument("--cmd", default="", help="Command to send (e.g. 'vermgmt bin')")
    p.add_argument("--keyword", default="", help="Keyword to search for in output")
    p.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    p.add_argument("--timeout", type=float, default=20.0, help="Max wait in seconds")
    p.add_argument("--output", default="", help="Evidence log path (auto if omitted)")
    p.add_argument("--context", type=int, default=5, help="Lines of context around match")
    p.add_argument("--type", choices=["sta", "cco"], default=None,
                    help="Target type for automatic /d/<type>/... evidence path")
    args = p.parse_args()

    edbg_root = "/home/ai_work/splc_tool/edbg_pc_debug_tool_full_source"
    if not Path(edbg_root).exists():
        _fail(f"EDBG source not found: {edbg_root}")

    powershell = _find_powershell()

    # Auto-generate evidence path in WSL /d/... format
    output_path = args.output
    if not output_path and args.type:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        label = PROJECT_LABELS.get(args.type, args.type)
        ev_dir = Path("/d") / args.type / label / stamp
        ev_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(ev_dir / f"splc-{args.port}-{stamp}")

    # Build the Windows-side Python script with WSL path (gets auto-converted to UNC for writing)
    win_script = _build_win_script(
        edbg_root=edbg_root,
        port=args.port,
        baud=args.baud,
        cmd=args.cmd,
        keyword=args.keyword,
        timeout_s=args.timeout,
        output_path=output_path,
        context_lines=args.context,
    )

    tmp = Path(tempfile.mktemp(suffix=".py", prefix="splc_grab_"))
    try:
        tmp.write_text(win_script)
        ps_cmd = [
            powershell,
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command",
            f'python -u "{_w2w(str(tmp))}"',
        ]
        result = subprocess.run(
            ps_cmd, capture_output=True, text=True,
            timeout=int(args.timeout) + 60,
        )
        if result.returncode != 0 and not result.stdout.strip():
            _fail(result.stderr.strip() or "PowerShell invocation failed")
        try:
            parsed = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            _fail(
                f"Failed to parse worker output. "
                f"stdout={result.stdout.strip()[:500]} "
                f"stderr={result.stderr.strip()[:500]}"
            )
        # Convert returned evidence_path from UNC back to WSL /d/ format
        if parsed.get("evidence_path"):
            parsed["evidence_path"] = _w2l(parsed["evidence_path"])
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        sys.exit(0 if parsed.get("ok") else 2)
    finally:
        if tmp.exists():
            tmp.unlink()


def _build_win_script(
    edbg_root, port, baud, cmd, keyword, timeout_s, output_path, context_lines,
):
    """Build the Python source that will run on the Windows side."""
    edbg_win = _w2w(edbg_root)
    output_win = _w2w(output_path) if output_path else ""

    return '''import sys, json, time
sys.path.insert(0, ''' + repr(edbg_win) + ''')
from edbg_pc.serial_backend import SerialBackend, SerialBackendError

port = ''' + repr(port) + '''
baud = ''' + str(baud) + '''
cmd = ''' + repr(cmd) + '''
keyword = ''' + repr(keyword) + '''
timeout_s = ''' + str(timeout_s) + '''
output_path = ''' + repr(output_win) + '''
context_lines = ''' + str(context_lines) + '''

try:
    ser = SerialBackend(port, baud, timeout=0.2)
    ser.open()
except SerialBackendError as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    sys.exit(2)

time.sleep(0.5)
ser.read_available()

if cmd:
    cmd_bytes = (cmd + "\\r\\n").encode("utf-8")
    ser.write(cmd_bytes)

deadline = time.monotonic() + timeout_s
buf = ""
matched = False
lines = []

while time.monotonic() < deadline:
    chunk = ser.read_available().decode("utf-8", errors="replace")
    if chunk:
        buf += chunk
        new_parts = chunk.split("\\n")
        if lines and new_parts:
            lines[-1] = lines[-1] + new_parts[0]
            lines.extend(new_parts[1:])
        else:
            lines.extend(new_parts)
        if keyword and keyword in buf and not matched:
            matched = True
            more_deadline = time.monotonic() + 3.0
            while time.monotonic() < more_deadline:
                extra = ser.read_available().decode("utf-8", errors="replace")
                if extra:
                    buf += extra
                    extra_parts = extra.split("\\n")
                    if lines:
                        lines[-1] = lines[-1] + extra_parts[0]
                        lines.extend(extra_parts[1:])
                    else:
                        lines.extend(extra_parts)
                else:
                    time.sleep(0.05)
            break
    else:
        time.sleep(0.02)

ser.close()

if output_path:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(buf)

matched_index = -1
if matched:
    char_count = 0
    for li, line in enumerate(lines):
        char_count += len(line) + 1
        if char_count > buf.find(keyword):
            matched_index = li
            break

context_start = max(0, matched_index - context_lines) if matched_index >= 0 else max(0, len(lines) - context_lines)
context_end = min(len(lines), matched_index + context_lines + 1) if matched_index >= 0 else len(lines)
context = lines[context_start:context_end]

result = {
    "ok": matched if keyword else True,
    "keyword": keyword,
    "matched": matched,
    "context": context,
    "total_lines": len(lines),
    "evidence_path": output_path,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if (matched if keyword else True) else 2)
'''


def _find_powershell():
    ps = shutil.which("powershell.exe")
    if not ps:
        raise RuntimeError(
            "powershell.exe not found in WSL PATH. "
            "Make sure /mnt/c/Windows/System32/WindowsPowerShell/v1.0/ "
            "is in your WSL PATH."
        )
    return ps


def _w2w(path):
    """Convert WSL path to Windows UNC path."""
    try:
        converted = subprocess.run(
            ["wslpath", "-w", path],
            capture_output=True, text=True, timeout=5,
        )
        if converted.returncode == 0:
            return converted.stdout.strip()
    except Exception:
        pass
    return path


def _w2l(path):
    """Convert Windows UNC path or native path back to WSL path.

    Handles:
        \\\\wsl.localhost\\Ubuntu-22.04\\d\\sta\\...  ->  /d/sta/...
        C:\\Users\\...  ->  (pass through, not in WSL)
        /d/sta/...  ->  /d/sta/...  (already WSL format)
    """
    if not path:
        return path
    # Already a WSL /d/ path
    if path.startswith("/"):
        return path
    # Try wslpath -u conversion
    try:
        converted = subprocess.run(
            ["wslpath", "-u", path],
            capture_output=True, text=True, timeout=5,
        )
        if converted.returncode == 0 and converted.stdout.strip():
            return converted.stdout.strip()
    except Exception:
        pass
    # Fallback: manual UNC to /d/ conversion
    # \\wsl.localhost\Ubuntu-22.04\d\...  ->  /d/...
    normalized = path.replace("\\\\", "/").replace("\\", "/")
    # Pattern: wsl.localhost/Ubuntu-22.04/d/...
    if "wsl.localhost" in normalized:
        parts = normalized.split("/")
        # Find the /d/... part after wsl.localhost/Ubuntu-22.04
        try:
            idx = next(i for i, p in enumerate(parts) if p in ("d", "e", "f", "c", "D", "E", "F", "C"))
            return "/" + "/".join(parts[idx:]).lower()
        except (StopIteration, IndexError):
            pass
    return path


def _fail(msg):
    print(json.dumps({"ok": False, "error": str(msg)}))
    sys.exit(2)


if __name__ == "__main__":
    main()
