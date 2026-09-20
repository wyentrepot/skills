#!/bin/bash
# ============================================================================
# build_cco.sh — CCO / ECU 固件版本编译打包一键脚本
#
# 背景: firmware-version-build 技能(CCO/ECU 层)的唯一执行路径。单次 build 调用
#       = 单编译; 多编译(正式版+测试版/多版本) = 多次 build 调用, 每次独立完成
#       备份→改宏→make clean→编译→预期 zip 名校验→归档→恢复头文件, 互不影响。
#
# 用法:
#   build_cco.sh [--repo <路径>] build <cco|ecu> <DI_QU_MODE> <SVERSION6> <VDATE6> <IDATE6>
#   build_cco.sh [--repo <路径>] --dry-run build <同上>     # 只打印将改的宏与预期 zip 名
#   build_cco.sh --repo /home/H_CCO/001/cco build ecu AN_HUI_MODE 002601 260910 260910
#
#   参数说明:
#     SVERSION6 = 大版本 6 位十六进制, 如 002601
#     VDATE6    = 版本日期 YYMMDD, 如 260910 (对应 yxsm_conf.h VER_YEAR/MONTH/DAY)
#     IDATE6    = 内部版本日期 YYMMDD, 如 260910 (对应 diqu_conf.h FC_VER_YEAR/MONTH/DAY)
#     小版本 FC_VERSION_L 与批次/地区UTF8 随 DI_QU_MODE 分支块生效, 无需传参
#
# 仓库定位（路径保护）:
#   优先级: --repo <路径> > $CCO_REPO 环境变量 > 从当前目录向上自动探测
#   未定位到合法 CCO 仓库（缺 app/{yxsm_conf,diqu_conf}.h/Makefile/目标）一律拒绝执行;
#   破坏性操作(make clean)只发生在定位到的仓库内，执行前打印"操作仓库"。
#
# 产物: --out <dir> 默认 archive_<target>/, 每次 build 生成独立子目录
#       <out>/sv<SVER>_d<VDATE>_id<IDATE>/{zip, flash, iap, upgrade, readme.txt}
#
# 前置: 目标仓库为 git 仓库; 版本头文件无未提交改动(可用 --force 跳过检查)。
# 安全: 编译完成立即归档并恢复头文件; 任一步失败由 trap 自动恢复头文件。
# ============================================================================
set -euo pipefail
shopt -s nullglob

die() { echo "错误: $*" >&2; exit 1; }

# ---------- 参数解析 ----------
CMD=""
SUB=""
TGT=""
DIQU_MODE_ARG=""
SVER=""
VDATE=""
IDATE=""
OUT=""
DRY_RUN=0
FORCE=0
REPO_ARG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run|-n) DRY_RUN=1; shift ;;
    --force|-f)   FORCE=1; shift ;;
    --repo)       REPO_ARG="$2"; shift 2 ;;
    --out)        OUT="$2"; shift 2 ;;
    -h|--help)    sed -n '2,30p' "$0"; exit 0 ;;
    build)        CMD=build; shift ;;
    -*) echo "未知参数: $1" >&2; exit 2 ;;
    *)
      case "${CMD:-}" in
        build)
          if [ -z "$TGT" ]; then TGT="$1"
          elif [ -z "$DIQU_MODE_ARG" ]; then DIQU_MODE_ARG="$1"
          elif [ -z "$SVER" ]; then SVER="$1"
          elif [ -z "$VDATE" ]; then VDATE="$1"
          elif [ -z "$IDATE" ]; then IDATE="$1"
          else die "build 参数过多: $1"
          fi
          ;;
        *) die "缺少子命令: 用法 build_cco.sh build <cco|ecu> <DI_QU_MODE> <SVERSION6> <VDATE6> <IDATE6>" ;;
      esac
      shift ;;
  esac
done

[ "$CMD" = build ] || die "缺少子命令 build"
[ -n "$TGT" ] || die "缺少目标: build <cco|ecu>"
case "$TGT" in cco|ecu) ;; *) die "目标必须是 cco 或 ecu, 收到: $TGT" ;; esac
[ -n "$DIQU_MODE_ARG" ] || die "缺少 DI_QU_MODE 参数"
[ -n "$SVER" ] && [[ "$SVER" =~ ^[0-9a-fA-F]{6}$ ]] || die "SVERSION 必须为 6 位十六进制, 收到: ${SVER:-空}"
[ -n "$VDATE" ] && [[ "$VDATE" =~ ^[0-9]{6}$ ]] || die "VDATE 必须为 6 位数字 YYMMDD, 收到: ${VDATE:-空}"
[ -n "$IDATE" ] && [[ "$IDATE" =~ ^[0-9]{6}$ ]] || die "IDATE 必须为 6 位数字 YYMMDD, 收到: ${IDATE:-空}"

# ---------- 仓库定位（路径保护） ----------
find_repo() {
  local dir="$1"
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/app/yxsm_conf.h" ] && \
       [ -f "$dir/app/diqu_conf.h" ] && \
       [ -f "$dir/Makefile" ] && grep -q '^cco:' "$dir/Makefile" 2>/dev/null; then
      echo "$dir"; return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

resolve_root() {
  if [ -n "$REPO_ARG" ]; then
    ROOT="$(cd "$REPO_ARG" 2>/dev/null && pwd)" || die "指定的仓库目录不存在: $REPO_ARG"
  elif [ -n "${CCO_REPO:-}" ]; then
    ROOT="$(cd "$CCO_REPO" 2>/dev/null && pwd)" || die "CCO_REPO 环境变量指向的目录不存在: $CCO_REPO"
  else
    ROOT="$(find_repo "$(pwd)")" || \
      die "未定位到 CCO 仓库: 请用 --repo <路径> 指定，或进入仓库内任意子目录运行（自动向上探测）"
  fi
  { [ -f "$ROOT/app/yxsm_conf.h" ] && [ -f "$ROOT/app/diqu_conf.h" ]; } || \
    die "目标不是合法 CCO 仓库（缺 app/{yxsm_conf,diqu_conf}.h）: $ROOT"
  grep -q "^${TGT}:" "$ROOT/Makefile" 2>/dev/null || \
    die "目标仓库 Makefile 中不存在目标 $TGT: $ROOT"
  git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || \
    die "目标不是 git 仓库（脚本依赖 git 恢复头文件）: $ROOT"
}

resolve_root
echo "操作仓库: $ROOT  (目标: $TGT)"
cd "$ROOT"
H_YXSM="app/yxsm_conf.h"
H_DIQU="app/diqu_conf.h"
[ -n "$OUT" ] || OUT="archive_${TGT}"

# ---------- 前置检查 ----------
if [ "$FORCE" -ne 1 ]; then
  git diff --quiet -- "$H_YXSM" "$H_DIQU" || \
    die "版本头文件有未提交改动，先提交/暂存再运行（或加 --force）"
fi

# ---------- 公共 python: DI_QU_MODE 分支块解析 ----------
PY_BLOCKS='
import re
def blocks(src_lines):
    out = {}
    depth = 0; start = -1; cur = None
    START = re.compile(r"^#\s*(if|elif)\s+DI_QU_MODE\s*==\s*([A-Z_0-9]+)\s*$")
    IFL = re.compile(r"^#\s*if"); ENDIF = re.compile(r"^#\s*endif")
    TERM = re.compile(r"^#\s*(elif|else)\b")
    for i, l in enumerate(src_lines):
        s = l.strip()
        m = START.match(s)
        if m:
            if start >= 0 and depth == 1:
                out.setdefault(cur, []).append((start, i))
            start, cur, depth = i, m.group(2), 1
        elif start >= 0:
            if IFL.match(s):
                depth += 1
            elif ENDIF.match(s):
                depth -= 1
                if depth == 0:
                    out.setdefault(cur, []).append((start, i))
                    start = -1; cur = None
            elif TERM.match(s) and depth == 1:
                out.setdefault(cur, []).append((start, i))
                start = -1; cur = None; depth = 0
    return out
def macro_in(src_lines, blks, name):
    if not blks: return None
    pat = re.compile(r"^#define\s+" + re.escape(name) + r"\s+(.*?)\s*$")
    for a, b in blks:
        for l in src_lines[a:b]:
            m = pat.match(l.strip())
            if m:
                return re.split(r"/\*|//", m.group(1))[0].strip()
    return None
def global_macro(src_lines, name):
    pat = re.compile(r"^#define\s+" + re.escape(name) + r"\s+(.*?)\s*$")
    for l in src_lines:
        m = pat.match(l.strip())
        if m:
            return re.split(r"/\*|//", m.group(1))[0].strip()
    return None
'

# ---------- 读取基线状态 ----------
read_state() {
  {
    echo "$PY_BLOCKS"
    cat <<'BODY'
import sys, re
hy, hd = sys.argv[1], sys.argv[2]
def lines(p): return open(p, encoding="utf-8").read().split("\n")
y = lines(hy); d = lines(hd)
yb = blocks(y)
# 当前 DI_QU_MODE 名与数值
mode = ""
for l in d:
    m = re.match(r"^#define\s+DI_QU_MODE\s+([A-Z_0-9]+)", l)
    if m: mode = m.group(1); break
modeval = ""
for l in d:
    m = re.match(r"^#define\s+" + re.escape(mode) + r"\s+(0x[0-9a-fA-F]+)", l)
    if m: modeval = m.group(1); break
# FC_VERSION_L(全局) / FC_VER_*(全局)
fcv = ""
for l in d:
    m = re.match(r"^#define\s+FC_VERSION_L\s+(0x[0-9a-fA-F]+)", l)
    if m: fcv = m.group(1); break
fcv = int(fcv, 16) if fcv else 0
def numv(s, default=""):
    if not s: return default
    m = re.search(r"0x([0-9a-fA-F]+)", s)
    return m.group(1) if m else default
fcv_y = numv(global_macro(d, "FC_VER_YEAR"))
fcv_m = numv(global_macro(d, "FC_VER_MONTH"))
fcv_d = numv(global_macro(d, "FC_VER_DAY"))
print(f"DIQU_MODE={mode}")
print(f"DIQU_VAL={modeval}")
print(f"FCVER_L={fcv}")
print(f"FCVER_Y={fcv_y} FCVER_M={fcv_m} FCVER_D={fcv_d}")
BODY
  } | python3 - "$H_YXSM" "$H_DIQU"
}

# ---------- 改宏 ----------
set_block_macro() {
  {
    echo "$PY_BLOCKS"
    cat <<'BODY'
import sys, re
path, mode, macro, newval = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
lines = open(path, encoding="utf-8").read().split("\n")
pat = re.compile(r"^(\s*#define\s+" + re.escape(macro) + r"\s+).*$")
for a, b in blocks(lines).get(mode, []):
    for i in range(a, b):
        m = pat.match(lines[i])
        if m:
            lines[i] = m.group(1) + newval
            open(path, "w", encoding="utf-8").write("\n".join(lines))
            sys.exit(0)
sys.exit(f"set_block_macro: 在 {path} 的 {mode} 分支块中找不到宏 {macro}")
BODY
  } | python3 - "$1" "$DIQU_MODE_ARG" "$2" "$3"
}

set_global_macro() {
  {
    echo "$PY_BLOCKS"
    cat <<'BODY'
import sys, re
path, macro, newval = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path, encoding="utf-8").read().split("\n")
pat = re.compile(r"^(\s*#define\s+" + re.escape(macro) + r"\s+).*$")
n = 0
for i, l in enumerate(lines):
    m = pat.match(l)
    if m:
        lines[i] = m.group(1) + newval
        n += 1
if n == 0:
    sys.exit(f"set_global_macro: 在 {path} 中找不到宏 {macro}")
open(path, "w", encoding="utf-8").write("\n".join(lines))
BODY
  } | python3 - "$1" "$2" "$3"
}

# ---------- 恢复头文件 ----------
restore_headers() {
  git checkout -- "$H_YXSM" "$H_DIQU" 2>/dev/null || true
}
trap 'restore_headers' EXIT

# ---------- 基线解析 ----------
STATE="$(read_state)"
eval "$(echo "$STATE" | sed 's/^/BASE_/')"
# 校验传入的 DI_QU_MODE 存在于模式表
DIQU_MODE_VAL="$(grep -oP "^#define\s+${DIQU_MODE_ARG}\s+\K0x[0-9a-fA-F]+" "$H_DIQU" | head -1 || true)"
[ -n "$DIQU_MODE_VAL" ] || die "模式表(app/diqu_conf.h)中不存在 DI_QU_MODE: $DIQU_MODE_ARG"

# 日期参数 → BCD 十六进制 (260916 -> 0x26 0x09 0x16; 逐位 BCD, 不能用十进制整体转换)
bcd_hex() { printf "0x%02X" "$(( 10#${1:0:1} * 16 + 10#${1:1:1} ))"; }
VD_Y=$(bcd_hex "${VDATE:0:2}"); VD_M=$(bcd_hex "${VDATE:2:2}"); VD_D=$(bcd_hex "${VDATE:4:2}")
ID_Y=$(bcd_hex "${IDATE:0:2}"); ID_M=$(bcd_hex "${IDATE:2:2}"); ID_D=$(bcd_hex "${IDATE:4:2}")

SVER_NUM=$((0x$SVER))
ISV=$(( (DIQU_MODE_VAL << 16) | BASE_FCVER_L ))
ISV_F="$(printf "%06x" "$ISV")"
ARCH_DIR="$OUT/sv${SVER}_d${VDATE}_id${IDATE}"

echo "== CCO/ECU 编译 =="
echo "  模式=$DIQU_MODE_ARG(0x$(printf %x "$DIQU_MODE_VAL"))  大版本=0x$SVER  版本日期=$VDATE  内部日期=$IDATE"
echo "  小版本 FC_VERSION_L=0x$(printf %04x "$BASE_FCVER_L") (随模式分支, 不修改)"
echo "  预期 isv=$(printf %06x "$ISV")  预期 zip: *sv${SVER}-${VDATE}*isv${ISV_F}-idate${IDATE}-*.zip"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "== 干跑模式: 将修改以下宏 =="
  echo "  $H_DIQU: DI_QU_MODE -> $DIQU_MODE_ARG"
  echo "  $H_YXSM ($DIQU_MODE_ARG 分支): SVERSION -> ((uint32_t)(0x$SVER))"
  echo "  $H_YXSM ($DIQU_MODE_ARG 分支): VER_YEAR/MONTH/DAY -> $VD_Y/$VD_M/$VD_D"
  echo "  $H_DIQU (全局): FC_VER_YEAR/MONTH/DAY -> $ID_Y/$ID_M/$ID_D"
  exit 0
fi

# ---------- 改宏 ----------
set_global_macro "$H_DIQU" "DI_QU_MODE" "$DIQU_MODE_ARG"
set_block_macro "$H_YXSM" "SVERSION" "((uint32_t)(0x$SVER))"
set_block_macro "$H_YXSM" "VER_YEAR" "($VD_Y)"
set_block_macro "$H_YXSM" "VER_MONTH" "($VD_M)"
set_block_macro "$H_YXSM" "VER_DAY" "($VD_D)"
set_global_macro "$H_DIQU" "FC_VER_YEAR" "($ID_Y)"
set_global_macro "$H_DIQU" "FC_VER_MONTH" "($ID_M)"
set_global_macro "$H_DIQU" "FC_VER_DAY" "($ID_D)"
echo "  已写入版本宏"

# ---------- 编译 ----------
LOG_DIR="$ROOT/build_logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/${TGT}_${DIQU_MODE_ARG}_sv${SVER}_${VDATE}_${IDATE}.log"
echo "  [编译中, 日志 $LOG]"
if ! make clean >"$LOG" 2>&1; then
  die "make clean 失败，日志: $LOG"
fi
if ! make "$TGT" jump >>"$LOG" 2>&1; then
  tail -15 "$LOG" >&2
  die "编译失败，日志: $LOG"
fi

# ---------- 校验 + 归档 ----------
zips=( firmware/*sv${SVER}-${VDATE}*isv${ISV_F}-idate${IDATE}-*.zip )
if [ ${#zips[@]} -eq 0 ]; then
  echo "  警告: 未找到预期 zip (sv$SVER-$VDATE ... isv$ISV_F-idate$IDATE)，实际产物:" >&2
  ls firmware/*.zip >&2 2>/dev/null || true
  die "产物 zip 校验未通过，日志: $LOG"
fi
grep -oE "固件打包完成!|zip firmware package ok! -> .*" "$LOG" | tail -1 || echo "(未找到打包成功日志)"

mkdir -p "$ARCH_DIR"
cp "${zips[0]}" firmware/*.bin firmware/*.dat firmware/readme.txt "$ARCH_DIR/"
echo "  已归档 -> $ARCH_DIR/ ($(basename "${zips[0]}"))"

restore_headers
rm -rf "$LOG_DIR"
echo "  头文件已恢复"
echo "完成。交付目录: $ROOT/$ARCH_DIR"
