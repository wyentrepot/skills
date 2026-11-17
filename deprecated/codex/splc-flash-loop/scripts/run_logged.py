#!/usr/bin/env python3
"""Run a command silently, save full output, and emit compact timed JSON."""

import argparse
import subprocess
import time
from pathlib import Path

from compact_log import bounded_context, select_indices, write_json


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument(
        "--kind",
        choices=("auto", "build", "pytest", "unity", "serial"),
        default="auto",
    )
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--context", type=int, default=6)
    parser.add_argument("--max-lines", type=int, default=80)
    parser.add_argument("--max-chars", type=int, default=500)
    parser.add_argument("--cwd")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def main():
    args = parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    timed_out = False
    with args.log.open("wb") as stream:
        try:
            result = subprocess.run(
                args.command,
                cwd=args.cwd,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=args.timeout,
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = 124
    elapsed = time.perf_counter() - started
    raw = args.log.read_bytes()
    lines = raw.decode("utf-8", errors="replace").splitlines()
    indices = select_indices(lines, args.kind, args.keyword)
    evidence = (
        []
        if exit_code == 0 and not indices
        else bounded_context(
            lines, indices, args.context, args.max_lines, args.max_chars
        )
    )
    output = {
        "command": args.command,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 3),
        "log": str(args.log.resolve()),
        "summary": {
            "kind": args.kind,
            "source_bytes": len(raw),
            "source_lines": len(lines),
            "matched_lines": len(indices),
            "emitted_lines": len(evidence),
            "truncated": len(evidence) < len(lines),
            "evidence": evidence,
        },
    }
    write_json(output)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
