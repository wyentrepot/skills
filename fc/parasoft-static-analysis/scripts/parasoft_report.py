#!/usr/bin/env python3
"""Filter a Parasoft C++test report.xml and output totals plus findings."""
import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

VIOLATION_TAGS = {"StdViol", "FlowViol"}


def relative_file(location: str, repo: Path) -> str:
    """Map Parasoft's absolute/product alias path to a Git-relative path."""
    if not location:
        return ""
    try:
        return str(Path(location).resolve().relative_to(repo.resolve()))
    except ValueError:
        pass
    # Typical C++test BDF reports map a product root to /product/<name>/.
    marker = "/product/"
    if marker in location:
        tail = location.split(marker, 1)[1]
        return tail.split("/", 1)[1] if "/" in tail else tail
    return location.lstrip("/")


def load_report(report: Path, repo: Path):
    root = ET.parse(report).getroot()
    result = []
    for node in root.iter():
        if node.tag not in VIOLATION_TAGS:
            continue
        a = node.attrib
        try:
            severity, line = int(a.get("sev", "0")), int(a.get("ln", "0"))
        except ValueError:
            continue
        result.append({
            "severity": severity,
            "file": relative_file(a.get("locFile", ""), repo),
            "line": line,
            "rule": a.get("rule", ""),
            "message": " ".join(a.get("msg", "").split()),
        })
    return result


def added_lines(repo: Path, commit: str):
    """Read new-side line numbers from commit^..commit, including new files."""
    output = subprocess.check_output(
        ["git", "-C", str(repo), "diff", "--no-ext-diff", "--unified=0", f"{commit}^", commit],
        text=True, stderr=subprocess.STDOUT,
    )
    files = collections.defaultdict(set)
    current = None
    for row in output.splitlines():
        if row.startswith("+++ b/"):
            current = row[6:]
        elif row.startswith("+++ /dev/null"):
            current = None
        elif current and row.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", row)
            if match:
                start, size = int(match.group(1)), int(match.group(2) or 1)
                files[current].update(range(start, start + size))
    return files


def fingerprint(item):
    # Intentionally omit line: unchanged violations can move when earlier lines change.
    return item["file"], item["rule"], item["message"]


def format_counts(items):
    counts = collections.Counter(item["severity"] for item in items)
    return "，".join(f"S{severity}={counts[severity]}" for severity in sorted(counts)) or "无"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path, help="current report.xml")
    parser.add_argument("--repo", required=True, type=Path, help="analysed Git repository root")
    parser.add_argument("--commit", help="keep only findings on lines added by this commit")
    parser.add_argument("--baseline", type=Path, help="baseline report.xml")
    parser.add_argument("--new-only", action="store_true", help="keep only findings absent from baseline")
    parser.add_argument("--levels", default="1,2", help="listed severity values, comma-separated (default: 1,2)")
    parser.add_argument("--format", choices=("markdown", "tsv"), default="markdown")
    args = parser.parse_args()
    if args.new_only and not args.baseline:
        parser.error("--new-only requires --baseline")
    try:
        levels = {int(value) for value in args.levels.split(",") if value.strip()}
    except ValueError:
        parser.error("--levels must be integers, for example: 1,2,3")

    current = load_report(args.report, args.repo)
    scoped = current
    scope = "完整报告"
    if args.commit:
        changed = added_lines(args.repo, args.commit)
        scoped = [item for item in scoped if item["line"] in changed.get(item["file"], set())]
        scope = f"提交 {args.commit} 的新增行"
    if args.new_only:
        old = {fingerprint(item) for item in load_report(args.baseline, args.repo)}
        scoped = [item for item in scoped if fingerprint(item) not in old]
        scope += "；相对基线新增"
    listed = [item for item in scoped if item["severity"] in levels]
    listed.sort(key=lambda item: (item["severity"], item["file"], item["line"], item["rule"]))

    print(f"完整报告严重等级总数：{format_counts(current)}")
    print(f"筛选范围（{scope}）严重等级总数：{format_counts(scoped)}")
    print(f"待列出等级（{','.join(map(str, sorted(levels)))})：{len(listed)} 项")
    if args.format == "tsv":
        print("severity\tfile\tline\trule\tmessage")
        for item in listed:
            print(f"{item['severity']}\t{item['file']}\t{item['line']}\t{item['rule']}\t{item['message']}")
        return
    print("| 严重等级 | 文件:行号 | 规则 | 问题描述 |")
    print("|---:|---|---|---|")
    for item in listed:
        message = item["message"].replace("|", "\\|")
        print(f"| {item['severity']} | `{item['file']}:{item['line']}` | `{item['rule']}` | {message} |")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ET.ParseError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)
