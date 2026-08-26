"""P2 observe-workbench-logs 客户端：显式调用、默认 dry-run、六命令只读。

只消费 P1 已冻结的 /api/ai/v1 观察与证据接口（docs/03-骨架设计.md §6.3）。
安全边界（docs/04-任务安排.md P2 与交接报告 §4）：
- 只能显式 $observe-workbench-logs 调用；allow_implicit_invocation 由 agents/openai.yaml 固定为 false。
- Token 唯一来自 WORKBENCH_AI_TOKEN 环境变量；不接受 token CLI 参数、配置文件值或 URL userinfo，
  且任何输出/异常/调试都不回显明文 Token。
- 默认 dry-run：只输出规范化、脱敏的请求计划，零 HTTP、零 operation。
  只有显式 --execute 才允许发出 HTTP；其中 observe 的 POST 还需既有 session/index 目标。
- 不提供 ensure/start/stop/send/flash/烧录/串口打开/文件系统扫描/cancel 能力。
- wait 单次服务端 timeout 不超过 30 秒，终态即停止，绝不发送 cancel。

只使用标准库（urllib.request），无第三方依赖。
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# 默认仅允许本机工作台地址（骨架设计 §6.3）
DEFAULT_BASE_URL = "http://127.0.0.1:8790"
TOKEN_ENV = "WORKBENCH_AI_TOKEN"

TERMINAL_STATES = {"matched", "timed_out", "cancelled", "error", "interrupted", "source_stopped"}

# 危险命令白名单之外的动作——本客户端绝不提供（由 argparse 子命令集合天然保证，无独立代码）


class ClientError(Exception):
    """安全失败：脱敏、可读、退出码非零。"""


# 高熵 Token 形态：长度 ≥ 20 且不含空白（避免把普通路径/ID 误打码）
_TOKEN_LIKE = re.compile(r"^[A-Za-z0-9._~+/=-]{20,}$")


def _redact(value: str) -> str:
    """脱敏：实际 Token、Token 形态串、Bearer 头、URL userinfo 一律打码。"""
    if not value:
        return value
    token = os.environ.get(TOKEN_ENV, "").strip()
    if token:
        value = value.replace(token, "<redacted>")
    # Authorization: Bearer <token> 整体打码
    if value.startswith("Bearer "):
        return "Bearer <redacted>"
    # 独立的 token 形态串打码
    if _TOKEN_LIKE.fullmatch(value.strip()):
        return "<redacted>"
    return value


def _load_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise ClientError(
            f"缺少授权 Token：请设置环境变量 {TOKEN_ENV}（不得用命令行参数传入）。"
        )
    return token


def _normalize_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ClientError(f"非法 base URL（仅允许 http/https）：{_redact(base_url)}")
    if parsed.username is not None or parsed.password is not None:
        raise ClientError("base URL 不得包含 userinfo（用户名/密码）")
    host = parsed.hostname or ""
    _require_loopback_host(host, base_url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _require_loopback_host(host: str, base_url: str) -> None:
    """只允许本机回环地址，避免 Authorization Token 离开本机工作台。"""
    lower = host.lower()
    if lower in ("localhost", ""):
        return
    candidate = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        addr = ipaddress.ip_address(candidate)
    except ValueError:
        raise ClientError(f"非法 base URL host：{_redact(base_url)}")
    if addr.is_loopback:
        return
    raise ClientError(f"拒绝非本机 base URL host：{_redact(base_url)}（仅允许 loopback）")


def transport_request(method: str, url: str, *, headers: dict | None = None,
                      body: bytes | None = None, timeout: float | None = None) -> dict:
    """标准库 HTTP 传输层；测试通过 monkeypatch 替换本函数以零网络运行。"""
    req = urllib.request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        payload = {"detail": raw.decode("utf-8", errors="replace")[:500]}
    return {"status": status, "body": payload}


class Client:
    """六命令只读客户端；默认 dry-run。"""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, execute: bool = False):
        self.base_url = _normalize_base_url(base_url)
        self.execute = execute

    def _url(self, path: str) -> str:
        return self.base_url + path

    def _headers(self, token: str | None, extra_headers: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.update(extra_headers or {})
        return headers

    def _http(self, method: str, path: str, *, body: dict | None = None,
              token: str | None = None, timeout: float | None = None,
              extra_headers: dict | None = None) -> dict:
        url = self._url(path)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = self._headers(token, extra_headers)
        if data is not None:
            headers["Content-Type"] = "application/json"
        return transport_request(method, url, headers=headers, body=data, timeout=timeout)

    # -- 单命令实现（每个都先打印计划；execute 才发 HTTP）--------------------

    def status(self, token: str | None = None) -> dict:
        path = "/api/ai/v1/status"
        return self._maybe_execute("status", "GET", path, token=token)

    def observe(self, *, source: str, session_id: str | None, index_id: str | None,
                kind: str, value: str | None, frame_kind: str | None,
                selector: str, window: dict, client_request_id: str | None,
                token: str | None = None) -> dict:
        if source == "module_log":
            if not session_id:
                raise ClientError("module_log observe 必须提供 --session-id（既有后端会话）")
            if kind not in {"literal", "regex", "loghook_rule", "sequence", "not_seen"}:
                raise ClientError("module_log --kind 必须是文本日志匹配器")
            target: dict = {"session_id": session_id}
            match: dict = {"kind": kind}
            if value is not None:
                match["value"] = value
        elif source == "listener":
            if not index_id:
                raise ClientError("listener observe 必须提供 --index-id（既有索引）")
            if kind not in {"parsed_frame", "frame_query"} or not frame_kind:
                raise ClientError("listener 必须提供 --kind parsed_frame/frame_query 和 --frame-kind")
            target = {"index_id": index_id, "mapping_id": "listener-main"}
            match = {"kind": kind, "frame_kind": frame_kind, "selector": selector}
        else:
            raise ClientError(f"不支持的 source：{source}（仅 module_log / listener）")
        body = {
            "source": source,
            "target": target,
            "window": window,
            "match": match,
            "context": {"before": 20, "after": 30},
            "lifecycle": {"ensure_source_running": False, "on_finish": "leave_running"},
        }
        extra_headers = {"Idempotency-Key": client_request_id} if client_request_id else None
        return self._maybe_execute("observe", "POST", "/api/ai/v1/observations",
                                   body=body, token=token, extra_headers=extra_headers)

    def wait(self, operation_id: str, timeout_seconds: int = 30,
             token: str | None = None) -> dict:
        if timeout_seconds > 30:
            raise ClientError("wait 单次服务端 timeout 不得超过 30 秒")
        path = f"/api/ai/v1/operations/{urllib.parse.quote(operation_id)}/wait?timeout_seconds={timeout_seconds}"
        return self._maybe_execute("wait", "GET", path, token=token)

    def artifact(self, artifact_id: str, token: str | None = None) -> dict:
        path = f"/api/ai/v1/artifacts/{urllib.parse.quote(artifact_id)}"
        return self._maybe_execute("artifact", "GET", path, token=token)

    def listener_schema(self, token: str | None = None) -> dict:
        path = "/api/ai/v1/listener/schema"
        return self._maybe_execute("listener-schema", "GET", path, token=token)

    def frame_detail(self, index_id: str, frame_id: str, token: str | None = None) -> dict:
        path = (f"/api/ai/v1/listener/indexes/{urllib.parse.quote(index_id)}"
                f"/frames/{urllib.parse.quote(str(frame_id))}")
        return self._maybe_execute("frame-detail", "GET", path, token=token)

    # -- 执行骨架 -----------------------------------------------------------

    def _maybe_execute(self, action: str, method: str, path: str, *,
                       body: dict | None = None, token: str | None = None,
                       extra_headers: dict | None = None) -> dict:
        if not self.execute:
            # dry-run：只打印规范化、脱敏的请求计划，不发 HTTP、不建 operation
            plan = {
                "action": action,
                "method": method,
                "url": self.base_url + path,
                "body": body,
                "execute": False,
            }
            print(_redact(json.dumps(plan, ensure_ascii=False, indent=2)))
            return plan
        if token is None:
            token = _load_token()
        result = self._http(method, path, body=body, token=token, timeout=30.0,
                            extra_headers=extra_headers)
        if result["status"] >= 400:
            detail = result["body"].get("detail", result["body"])
            raise ClientError(f"{method} {path} 失败（HTTP {result['status']}）：{_redact(str(detail))}")
        print(_redact(json.dumps(result["body"], ensure_ascii=False, indent=2)))
        return result["body"]


def _parse_window(args: argparse.Namespace) -> dict:
    if args.mode == "live":
        return {"mode": "live", "start": "now", "timeout_seconds": args.timeout_seconds}
    if args.mode == "cursor_range" and args.source == "module_log":
        if args.start_seq is None or args.end_seq is None:
            raise ClientError("module cursor_range 必须提供 --start-seq 和 --end-seq")
        return {"mode": "cursor_range", "start_seq": args.start_seq, "end_seq": args.end_seq}
    if args.mode == "cursor_range" and args.source == "listener":
        if args.index_id is None or args.start_frame_id is None or args.end_frame_id is None:
            raise ClientError("listener cursor_range 必须提供 --index-id、--start-frame-id 和 --end-frame-id")
        return {"type": "cursor_range", "index_id": args.index_id,
                "start_frame_id": args.start_frame_id, "end_frame_id": args.end_frame_id}
    raise ClientError(f"暂不支持窗口模式：{args.mode}")


def _build_parser() -> argparse.ArgumentParser:
    # 公共参数：--base-url / --execute 既允许在顶层，也允许在子命令后出现
    root_common = argparse.ArgumentParser(add_help=False)
    root_common.add_argument("--base-url", default=DEFAULT_BASE_URL,
                             help=f"工作台地址（默认 {DEFAULT_BASE_URL}）")
    root_common.add_argument("--execute", action="store_true",
                             help="真正发出 HTTP（默认 dry-run 仅打印脱敏计划）")

    parser = argparse.ArgumentParser(
        prog="observe-workbench-logs",
        description="项目内 AI 观察技能客户端：显式调用、默认 dry-run、六命令只读。",
        parents=[root_common],
    )
    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument("--base-url", default=argparse.SUPPRESS,
                            help=f"工作台地址（默认 {DEFAULT_BASE_URL}）")
    sub_common.add_argument("--execute", action="store_true", default=argparse.SUPPRESS,
                            help="真正发出 HTTP（默认 dry-run 仅打印脱敏计划）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", parents=[sub_common], help="查询工作台/会话/观察任务状态")
    sub.add_parser("listener-schema", parents=[sub_common], help="查询侦听台帧语义与字段选择器")

    p_observe = sub.add_parser("observe", parents=[sub_common],
                               help="对既有 module session 或 listener index 创建观察")
    p_observe.add_argument("--source", choices=["module_log", "listener"], required=True)
    p_observe.add_argument("--session-id", help="module_log 既有后端会话")
    p_observe.add_argument("--index-id", help="listener 既有索引")
    p_observe.add_argument("--kind", choices=[
        "literal", "regex", "loghook_rule", "sequence", "not_seen", "parsed_frame", "frame_query",
    ], required=True)
    p_observe.add_argument("--value", help="module 文本匹配值或 rule_id")
    p_observe.add_argument("--frame-kind", help="listener 帧种类，如 central_beacon")
    p_observe.add_argument("--selector", choices=["first", "last", "all", "first_per_minute", "nth"],
                           default="first", help="listener 命中选择器")
    p_observe.add_argument("--mode", choices=["live", "cursor_range"], default="live")
    p_observe.add_argument("--timeout-seconds", type=int, default=120, help="live 模式超时（秒）")
    p_observe.add_argument("--start-seq", type=int, help="module cursor_range 起始 seq")
    p_observe.add_argument("--end-seq", type=int, help="module cursor_range 结束 seq")
    p_observe.add_argument("--start-frame-id", type=int, help="listener cursor_range 起始 frame_id")
    p_observe.add_argument("--end-frame-id", type=int, help="listener cursor_range 结束 frame_id")
    p_observe.add_argument("--client-request-id", help="observe 重试时复用的 Idempotency-Key")

    p_wait = sub.add_parser("wait", parents=[sub_common], help="有界轮询既有 operation 到终态")
    p_wait.add_argument("--operation-id", required=True)
    p_wait.add_argument("--timeout-seconds", type=int, default=30)

    p_artifact = sub.add_parser("artifact", parents=[sub_common], help="读取服务端登记的 Artifact")
    p_artifact.add_argument("--artifact-id", required=True)

    p_frame = sub.add_parser("frame-detail", parents=[sub_common],
                             help="读取侦听台帧详情（index_id + frame_id 复合深链）")
    p_frame.add_argument("--index-id", required=True)
    p_frame.add_argument("--frame-id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        client = Client(base_url=args.base_url, execute=args.execute)
        cmd = args.command
        token = None
        if cmd == "status":
            client.status()
        elif cmd == "listener-schema":
            client.listener_schema()
        elif cmd == "observe":
            window = _parse_window(args)
            token = _load_token() if args.execute else None
            client.observe(source=args.source, session_id=args.session_id,
                           index_id=args.index_id, kind=args.kind, value=args.value,
                           frame_kind=args.frame_kind, selector=args.selector, window=window,
                           client_request_id=args.client_request_id, token=token)
        elif cmd == "wait":
            client.wait(args.operation_id, timeout_seconds=args.timeout_seconds, token=token)
        elif cmd == "artifact":
            client.artifact(args.artifact_id, token=token)
        elif cmd == "frame-detail":
            client.frame_detail(args.index_id, args.frame_id, token=token)
        return 0
    except ClientError as exc:
        print(f"错误：{_redact(str(exc))}", file=sys.stderr)
        return 2
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - 安全失败：脱敏后非零退出
        print(f"错误：{_redact(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
