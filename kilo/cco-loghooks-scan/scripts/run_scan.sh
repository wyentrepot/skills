#!/usr/bin/env bash
# cco-loghooks-scan —— 一键运行入口
# 用法：
#   ./run_scan.sh <CCO源码根目录> <输出目录>
# 或通过环境变量：CCO_SRC=... CCO_OUT=... ./run_scan.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCO_SRC="${1:-${CCO_SRC:-}}"
CCO_OUT="${2:-${CCO_OUT:-}}"

if [[ -z "${CCO_SRC}" || -z "${CCO_OUT}" ]]; then
    echo "用法: ./run_scan.sh <CCO源码根目录> <输出目录>" >&2
    echo "或:  CCO_SRC=... CCO_OUT=... ./run_scan.sh" >&2
    exit 1
fi

if [[ ! -d "${CCO_SRC}" ]]; then
    echo "错误: CCO 源码目录不存在: ${CCO_SRC}" >&2
    exit 1
fi

mkdir -p "${CCO_OUT}"

export CCO_SRC
export CCO_OUT

echo "[1/3] 机械提取 LOG 语句 ..."
python3 "${HERE}/extract_logs.py"

echo "[2/3] 语义分类 ..."
python3 "${HERE}/classify_logs.py"

echo "[3/3] 生成汇总报告 ..."
python3 "${HERE}/summarize_logs.py"

echo "完成。产物输出到: ${CCO_OUT}"
ls -la "${CCO_OUT}" | grep cco_print_scan
