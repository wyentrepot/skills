#!/usr/bin/env python3
"""Emit bounded JSON evidence from a verbose build, test, or serial log."""

import argparse
import json
import re
import sys
from pathlib import Path


PATTERNS = {
    "build": [
        r"\bfatal error\b",
        r"\berror:",
        r"\bundefined reference\b",
        r"\bFAILED\b",
        r"make(?:\[\d+\])?: \*\*\*",
        r"\bwarning:",
        r"\b(?:built|build|image download) (?:succeeded|successful|ok)\b",
    ],
    "pytest": [
        r"^FAILED\b",
        r"^ERROR\b",
        r"\bTraceback \(most recent call last\)",
        r"=+ .* (?:failed|passed|error|errors)(?:,| in | =)",
    ],
    "unity": [
        r"\bFAIL(?:ED|URE|URES)?\b",
        r"\bASSERT",
        r"\b\d+ Tests? \d+ Failures? \d+ Ignored\b",
    ],
    "serial": [
        r"\bsversion\b",
        r"\bdiqu name\b",
        r"\bhversion\b",
        r"\bsver\b",
        r"\bisv\b",
        r"\bImage download OK\b",
        r"\bwarning\b",
        r"\berror\b",
        r"\btimeout\b",
    ],
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument(
        "--kind",
        choices=("auto", "build", "pytest", "unity", "serial"),
        default="auto",
    )
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--context", type=int, default=6)
    parser.add_argument("--max-lines", type=int, default=80)
    parser.add_argument("--max-chars", type=int, default=500)
    return parser.parse_args()


def select_indices(lines, kind, keywords):
    if keywords:
        lowered = [value.casefold() for value in keywords]
        return [
            index
            for index, line in enumerate(lines)
            if any(value in line.casefold() for value in lowered)
        ]
    patterns = (
        [pattern for group in PATTERNS.values() for pattern in group]
        if kind == "auto"
        else PATTERNS[kind]
    )
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    return [
        index
        for index, line in enumerate(lines)
        if any(pattern.search(line) for pattern in compiled)
    ]


def bounded_context(lines, indices, context, max_lines, max_chars=500):
    selected = []
    seen = set()
    for index in indices:
        for candidate in range(
            max(0, index - context), min(len(lines), index + context + 1)
        ):
            if candidate not in seen:
                selected.append(candidate)
                seen.add(candidate)
            if len(selected) >= max_lines:
                return truncate_lines(
                    [lines[item] for item in sorted(selected)], max_chars
                )
    if not selected:
        selected = list(range(max(0, len(lines) - min(20, max_lines)), len(lines)))
    return truncate_lines([lines[item] for item in sorted(selected)], max_chars)


def truncate_lines(lines, max_chars):
    marker = "...<truncated>"
    return [
        line
        if len(line) <= max_chars
        else line[: max_chars - len(marker)] + marker
        for line in lines
    ]


def write_json(value):
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")


def main():
    args = parse_args()
    if args.context < 0 or args.max_lines < 1 or args.max_chars < 32:
        raise SystemExit(
            "--context must be >= 0, --max-lines >= 1, and --max-chars >= 32"
        )
    raw = args.log.read_bytes()
    lines = raw.decode("utf-8", errors="replace").splitlines()
    indices = select_indices(lines, args.kind, args.keyword)
    evidence = bounded_context(
        lines, indices, args.context, args.max_lines, args.max_chars
    )
    result = {
        "path": str(args.log.resolve()),
        "kind": args.kind,
        "source_bytes": len(raw),
        "source_lines": len(lines),
        "matched_lines": len(indices),
        "emitted_lines": len(evidence),
        "truncated": len(evidence) < len(lines),
        "evidence": evidence,
    }
    write_json(result)


if __name__ == "__main__":
    main()
