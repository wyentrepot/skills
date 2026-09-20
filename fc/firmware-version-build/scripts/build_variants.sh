#!/bin/bash
# ============================================================================
# build_variants.sh — STA 大小版本差异固件一键编译打包
#
# 背景: firmware-version-build 技能(STA)的自动化执行器。技能原流程需 ~15 次
#       工具往返(查基线/备份/改宏/编译/归档/恢复/打包)，本脚本把除"编译耗时"
#       以外的全部机械步骤内聚，agent 只需: 确认基线 → 跑脚本 → 校验交付物。
#
# 变体规则(与技能版本表一致):
#   datong_xiaoyi  大同小异: 大版本(SVERSION/VERSION_DATE)同基线，
#                           小版本 FC_VERSION_L +1、小版本日期 INTERNAL_VER_DATE = 今日
#   xiaotong_dayi  小同大异: 小版本(FC_VERSION_L/INTERNAL_VER_DATE)同基线，
#                           大版本 SVERSION +1、大版本日期 VERSION_DATE = 今日
#
# 用法（脚本可放任意位置运行，唯一权威源在技能目录 scripts/，无需复制进仓库）:
#   build_variants.sh                                # 默认 TARGET=sta_venus2m_v7
#   build_variants.sh sta_venus2m                   # 指定目标
#   build_variants.sh --target sta_venus2m_v7 --variants "datong_xiaoyi xiaotong_dayi"
#   build_variants.sh --dry-run                     # 只打印版本矩阵与预期 zip 名，不编译
#
# 仓库定位（路径保护）:
#   优先级: --repo <路径> > $STA_REPO 环境变量 > 从当前目录向上自动探测
#   未定位到合法 STA 仓库（缺版本头文件/Makefile/目标）一律拒绝执行;
#   破坏性操作(make clean)只发生在定位到的仓库内，执行前会打印"操作仓库"。
#
# 产物:
#   archive_${TARGET}/{datong_xiaoyi,xiaotong_dayi}/    各变体全量产物(含 debug)
#   ${TARGET}_firmware.zip                              最终交付包(各变体仅 zip + 版本对照 readme)
#
# 前置: 仓库内运行（或指定 --repo/STA_REPO）; 版本头文件无未提交改动(可用 --force 跳过检查)。
# 安全: 每变体编译完成立即归档并恢复头文件; 任一步失败由 trap 自动恢复头文件。
# ============================================================================
set -euo pipefail
shopt -s nullglob

die() { echo "错误: $*" >&2; exit 1; }

# ---------- 参数解析 ----------
TARGET=""
VARIANTS="datong_xiaoyi xiaotong_dayi"
DRY_RUN=0
FORCE=0
REPO_ARG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run|-n) DRY_RUN=1; shift ;;
    --force|-f)   FORCE=1; shift ;;
    --repo)       REPO_ARG="$2"; shift 2 ;;
    --target)     TARGET="$2"; shift 2 ;;
    --variants)   VARIANTS="$2"; shift 2 ;;
    -h|--help)    sed -n '2,28p' "$0"; exit 0 ;;
    -*) echo "未知参数: $1" >&2; exit 2 ;;
    *)  TARGET="$1"; shift ;;
  esac
done
[ -z "$TARGET" ] && TARGET="sta_venus2m_v7"

# ---------- 仓库定位（路径保护） ----------
find_repo() {
  local dir="$1"
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/protocol/aps/diqu_conf.h" ] && \
       [ -f "$dir/protocol/aps/yxsm_conf.h" ] && \
       [ -f "$dir/Makefile" ] && grep -q '^sta_venus2m' "$dir/Makefile" 2>/dev/null; then
      echo "$dir"; return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

resolve_root() {
  if [ -n "$REPO_ARG" ]; then
    ROOT="$(cd "$REPO_ARG" 2>/dev/null && pwd)" || die "指定的仓库目录不存在: $REPO_ARG"
  elif [ -n "${STA_REPO:-}" ]; then
    ROOT="$(cd "$STA_REPO" 2>/dev/null && pwd)" || die "STA_REPO 环境变量指向的目录不存在: $STA_REPO"
  else
    ROOT="$(find_repo "$(pwd)")" || \
      die "未定位到 STA 仓库: 请用 --repo <路径> 指定，或进入仓库内任意子目录运行（自动向上探测）"
  fi
  # 二次校验: 必须是合法 STA 仓库且 git 仓库
  { [ -f "$ROOT/protocol/aps/diqu_conf.h" ] && [ -f "$ROOT/protocol/aps/yxsm_conf.h" ]; } || \
    die "目标不是合法 STA 仓库（缺 protocol/aps/{diqu_conf,yxsm_conf}.h）: $ROOT"
  grep -q "^${TARGET}:" "$ROOT/Makefile" 2>/dev/null || \
    die "目标仓库 Makefile 中不存在目标 $TARGET: $ROOT"
  git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || \
    die "目标不是 git 仓库（脚本依赖 git 恢复头文件）: $ROOT"
}

resolve_root
echo "操作仓库: $ROOT  (目标: $TARGET)"
cd "$ROOT"
H_DIQU="protocol/aps/diqu_conf.h"
H_YXSM="protocol/aps/yxsm_conf.h"
LOG_DIR="$ROOT/build_logs"

# ---------- 前置检查（仅剩余的头文件未提交改动检查） ----------
if [ "$FORCE" -ne 1 ]; then
  git diff --quiet -- "$H_DIQU" "$H_YXSM" || \
    die "版本头文件有未提交改动，先提交/暂存再运行（或加 --force）"
fi

# ---------- 公共 python: DI_QU_MODE 分支块解析 ----------
# 规则: "#if/#elif DI_QU_MODE == X" 既结束上一个块、又开启 X 的新块;
#       "#else"、非 DI_QU_MODE 的 "#elif"、以及深度归零的 "#endif" 结束当前块。
#       嵌套 #if/#endif 用深度跟踪，保证块边界正确。
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

# ---------- 读取基线版本状态 ----------
# 输出: DIQU_MODE / DIQU_VAL / SVERSION / YDATE_Y/M/D / FCVER_L / IDATE_Y/M/D / BATCH / REGION
read_state() {
  {
    echo "$PY_BLOCKS"
    cat <<'BODY'
import sys, re
hd, hy = sys.argv[1], sys.argv[2]
def lines(p): return open(p, encoding="utf-8").read().split("\n")

d = lines(hd); y = lines(hy)
mode = ""
for l in d:
    m = re.match(r"^#define\s+DI_QU_MODE\s+([A-Z_0-9]+)", l)
    if m: mode = m.group(1); break
modeval = ""
for l in d:
    m = re.match(r"^#define\s+" + re.escape(mode) + r"\s+(0x[0-9a-fA-F]+)", l)
    if m: modeval = m.group(1); break

db = blocks(d); yb = blocks(y)
def hexv(s, default="0x0"):
    if not s: return default
    m = re.search(r"0x[0-9a-fA-F]+", s)
    return m.group(0) if m else default
def numv(s, default=""):
    if not s: return default
    m = re.search(r"(\d+)ul?", s)
    return m.group(1) if m else default

sv  = hexv(macro_in(y, yb.get(mode), "SVERSION"))
yd  = [numv(macro_in(y, yb.get(mode), n)) for n in ("VERSION_DATE_Y","VERSION_DATE_M","VERSION_DATE_D")]
fc  = hexv(macro_in(d, db.get(mode), "FC_VERSION_L"))
id_ = [numv(global_macro(d, n)) for n in ("INTERNAL_VER_DATE_Y","INTERNAL_VER_DATE_M","INTERNAL_VER_DATE_D")]
batch = (macro_in(d, db.get(mode), "BATCH_NUM") or "").strip('"')
# 地区名: 优先解码 DI_QU_UTF8 字节（0xE5,0xAE,0x89,... -> 安徽）
utf8 = macro_in(d, db.get(mode), "DI_QU_UTF8")
if utf8:
    region = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", utf8)).decode("utf-8", errors="replace")
else:
    region = (macro_in(d, db.get(mode), "DIQU_PRINTF_STRING") or "").strip('"()')

print(f"DIQU_MODE={mode}")
print(f"DIQU_VAL={modeval}")
print(f"SVERSION={sv}")
print(f"YDATE_Y={yd[0]}")
print(f"YDATE_M={yd[1]}")
print(f"YDATE_D={yd[2]}")
print(f"FCVER_L={fc}")
print(f"IDATE_Y={id_[0]}")
print(f"IDATE_M={id_[1]}")
print(f"IDATE_D={id_[2]}")
print(f"BATCH={batch}")
print(f"REGION={region}")
BODY
  } | python3 - "$H_DIQU" "$H_YXSM"
}

# ---------- 改宏 ----------
# set_block_macro <file> <macro> <newval>  在 mode 所有分支块中定位并修改目标宏
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
  } | python3 - "$1" "$DIQU_MODE" "$2" "$3"
}

# set_global_macro <file> <macro> <newval>  全局唯一宏（INTERNAL_VER_DATE_*）
set_global_macro() {
  python3 - "$1" "$2" "$3" <<'PY'
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
PY
}

# ---------- 恢复头文件 ----------
restore_headers() {
  git checkout -- "$H_DIQU" "$H_YXSM" 2>/dev/null || true
}
trap 'restore_headers' EXIT

# ---------- 解析基线 ----------
STATE="$(read_state)"
eval "$(echo "$STATE" | sed 's/^/BASE_/')"
SVERSION=$((BASE_SVERSION))
FCVER_L=$((BASE_FCVER_L))
DIQU_VAL=$((BASE_DIQU_VAL))
DIQU_MODE="$BASE_DIQU_MODE"
# V7 平台标识: 目标名含 v7 即 PLATFORM=1（与 Makefile 的 VENUS_V7 定义对应）
if [[ "$TARGET" == *v7* ]]; then PLATFORM=1; else PLATFORM=0; fi

TODAY_Y=$(date +%-y); TODAY_M=$(date +%-m); TODAY_D=$(date +%-d)

# 变体 → (新SVERSION 新YDATE_Y/M/D 新FCVER_L 新IDATE_Y/M/D)
variant_values() {
  case "$1" in
    datong_xiaoyi)
      printf "%d %d %d %d %d %d %d %d" \
        "$SVERSION" "$BASE_YDATE_Y" "$BASE_YDATE_M" "$BASE_YDATE_D" \
        "$((FCVER_L+1))" "$TODAY_Y" "$TODAY_M" "$TODAY_D" ;;
    xiaotong_dayi)
      printf "%d %d %d %d %d %d %d %d" \
        "$((SVERSION+1))" "$TODAY_Y" "$TODAY_M" "$TODAY_D" \
        "$FCVER_L" "$BASE_IDATE_Y" "$BASE_IDATE_M" "$BASE_IDATE_D" ;;
    *)
      die "未知变体: $1（支持: datong_xiaoyi xiaotong_dayi）" ;;
  esac
}

fmt6()  { printf "%06x" "$1"; }
fmt2d() { printf "%02d%02d%02d" "$1" "$2" "$3"; }

# 预期 zip 名: ${REGION}-${BATCH}-STA-sv${mSVer}-${date}-isv${isv}-idate${idate}-1.zip
expected_zipname() {
  local sver=$1 datef=$2 fcv=$3 idatef=$4
  local isv=$(( DIQU_VAL << 16 | PLATFORM << 12 | fcv ))
  echo "${BASE_REGION}-${BASE_BATCH}-STA-sv$(fmt6 "$sver")-${datef}-isv$(fmt6 "$isv")-idate${idatef}-1.zip"
}

apply_edits() {
  local sver=$1 y=$2 m=$3 d=$4 fcv=$5 iy=$6 im=$7 id=$8
  set_block_macro "$H_YXSM" SVERSION "((uint32_t)(0x$(fmt6 "$sver")))"
  set_block_macro "$H_YXSM" VERSION_DATE_Y "${y}ul"
  set_block_macro "$H_YXSM" VERSION_DATE_M "${m}ul"
  set_block_macro "$H_YXSM" VERSION_DATE_D "${d}ul"
  set_block_macro "$H_DIQU" FC_VERSION_L "0x$(printf "%03x" "$fcv")"
  set_global_macro "$H_DIQU" INTERNAL_VER_DATE_Y "${iy}ul"
  set_global_macro "$H_DIQU" INTERNAL_VER_DATE_M "${im}ul"
  set_global_macro "$H_DIQU" INTERNAL_VER_DATE_D "${id}ul"
}

# ---------- 编译 + 归档单个变体 ----------
build_variant() {
  local v=$1
  read -r NSV NY NM ND NFC NIY NIM NID <<<"$(variant_values "$v")"
  local datef idatef
  datef=$(fmt2d "$NY" "$NM" "$ND")
  idatef=$(fmt2d "$NIY" "$NIM" "$NID")
  local zipname
  zipname=$(expected_zipname "$NSV" "$datef" "$NFC" "$idatef")

  echo "===== 变体 [$v]  $(date +%H:%M:%S) ====="
  echo "  大版本 SVERSION=$(fmt6 "$NSV")  大版本日期=$datef"
  echo "  小版本 FC_VERSION_L=0x$(printf %03x "$NFC")  小版本日期=$idatef"
  echo "  预期 zip: $zipname"

  apply_edits "$NSV" "$NY" "$NM" "$ND" "$NFC" "$NIY" "$NIM" "$NID"
  echo "  已写入版本宏"

  mkdir -p "$LOG_DIR"
  local log="$LOG_DIR/${TARGET}_${v}.log"
  echo "  [编译中, 日志 $log]"
  if ! make clean >"$log" 2>&1; then
    die "make clean 失败，日志: $log"
  fi
  if ! make "$TARGET" jump >>"$log" 2>&1; then
    tail -15 "$log" >&2
    die "编译失败($v)，日志: $log"
  fi

  local zips=( firmware/"$TARGET"/*sv"$(fmt6 "$NSV")"-"$datef"*isv*-idate"$idatef"-*.zip )
  if [ ${#zips[@]} -eq 0 ]; then
    echo "  警告: 未找到预期 zip (sv$(fmt6 "$NSV")-$datef ... idate$idatef)，实际产物:" >&2
    ls firmware/"$TARGET"/*.zip >&2 2>/dev/null || true
    die "产物 zip 校验未通过，日志: $log"
  fi
  grep -o "zip firmware package ok! -> .*" "$log" | tail -1 || echo "(未找到打包成功日志)"

  mkdir -p "archive_$TARGET/$v"
  cp "${zips[0]}" firmware/"$TARGET"/*.bin firmware/"$TARGET"/*.dat \
     firmware/"$TARGET"/readme.txt "archive_$TARGET/$v/"
  cp -r firmware/"$TARGET"/debug "archive_$TARGET/$v/debug"
  echo "  已归档 -> archive_$TARGET/$v/ ($(basename "${zips[0]}"))"

  restore_headers
  echo "  头文件已恢复"
}

# ---------- 最终打包 ----------
package() {
  echo "===== 打包最终交付 zip ====="
  local fw="$ROOT/${TARGET}_firmware.zip"
  for v in $VARIANTS; do
    rm -f "archive_$TARGET/$v"/*.bin "archive_$TARGET/$v"/*.dat \
          "archive_$TARGET/$v"/readme.txt
    rm -rf "archive_$TARGET/$v"/debug
  done

  local readme="archive_$TARGET/readme.txt"
  {
    echo "================================================================================"
    echo "${BASE_REGION} v7 (${TARGET}) 大小版本差异固件包"
    echo "生成日期: $(date +%Y-%m-%d)"
    echo "--------------------------------------------------------------------------------"
    printf "%-16s %-12s %-10s %-13s %-10s\n" "变体" "大版本SVERSION" "大版本日期" "小版本FC_VERSION_L" "小版本日期"
    echo "--------------------------------------------------------------------------------"
    printf "%-16s 0x%06x     %s      0x%03x        %s\n" \
      "基线baseline" "$SVERSION" "$(fmt2d "$BASE_YDATE_Y" "$BASE_YDATE_M" "$BASE_YDATE_D")" \
      "$FCVER_L" "$(fmt2d "$BASE_IDATE_Y" "$BASE_IDATE_M" "$BASE_IDATE_D")"
    for v in $VARIANTS; do
      read -r NSV NY NM ND NFC NIY NIM NID <<<"$(variant_values "$v")"
      printf "%-16s 0x%06x     %s      0x%03x        %s\n" \
        "$v" "$NSV" "$(fmt2d "$NY" "$NM" "$ND")" "$NFC" "$(fmt2d "$NIY" "$NIM" "$NID")"
    done
    echo "--------------------------------------------------------------------------------"
    echo "公共信息: 地区=${BASE_REGION}(${BASE_DIQU_MODE}=0x$(printf %x "$DIQU_VAL")) 批次=${BASE_BATCH}"
    echo "         平台=V$( [ $PLATFORM -eq 1 ] && echo 7 || echo 2 )  FC_SVERSION=(DI_QU_MODE<<16)|(PLATFORM<<12)|FC_VERSION_L"
    echo
    echo "变体含义:"
    echo "  datong_xiaoyi 大同小异: 大版本同基线, 小版本FC_VERSION_L+1、小版本日期=今日"
    echo "  xiaotong_dayi 小同大异: 小版本同基线, 大版本SVERSION+1、大版本日期=今日"
    echo
    echo "zip 文件名(含中文地区名, 非中文终端可能乱码)与 ASCII 对应:"
    for v in $VARIANTS; do
      local z
      z="$(ls "archive_$TARGET/$v"/*.zip 2>/dev/null | head -1)"
      [ -n "$z" ] && echo "  $(basename "$z")   <- $v"
    done
    echo
    echo "每个 zip 内含: flash_sta*_*.bin 生产烧录 / iap_*.bin 在线升级 / upgrade_*.dat 串口升级 / readme.txt"
    echo "=================================================================================="
  } > "$readme"

  rm -f "$fw"
  (cd "archive_$TARGET" && zip -qr "../$(basename "$fw")" .)
  echo "交付包: $fw"
}

# ---------- 干跑模式 ----------
if [ "$DRY_RUN" -eq 1 ]; then
  echo "== 干跑模式(不编译) =="
  echo "TARGET=$TARGET  变体=[$VARIANTS]  今日=$(date +%Y-%m-%d)  基线: ${BASE_REGION}/${BASE_BATCH} sv$(fmt6 "$SVERSION") isv$(fmt6 "$(( DIQU_VAL<<16|PLATFORM<<12|FCVER_L ))")"
  echo
  printf "%-16s %-9s %-8s %-12s %-9s %s\n" "变体" "SVERSION" "VDATE" "FC_VERSION_L" "IDATE" "预期zip名"
  for v in $VARIANTS baseline; do
    if [ "$v" = baseline ]; then
      NSV=$SVERSION; NY=$BASE_YDATE_Y; NM=$BASE_YDATE_M; ND=$BASE_YDATE_D
      NFC=$FCVER_L; NIY=$BASE_IDATE_Y; NIM=$BASE_IDATE_M; NID=$BASE_IDATE_D
    else
      read -r NSV NY NM ND NFC NIY NIM NID <<<"$(variant_values "$v")"
    fi
    printf "%-16s 0x%-8s %s 0x%-9s %s %s\n" "$v" "$(fmt6 "$NSV")" "$(fmt2d "$NY" "$NM" "$ND")" \
      "$(printf %03x "$NFC")" "$(fmt2d "$NIY" "$NIM" "$NID")" \
      "$(expected_zipname "$NSV" "$(fmt2d "$NY" "$NM" "$ND")" "$NFC" "$(fmt2d "$NIY" "$NIM" "$NID")")"
  done
  exit 0
fi

# ---------- 主流程 ----------
echo "== STA 大小版本差异编译 =="
echo "TARGET=$TARGET  变体=[$VARIANTS]  基线: ${BASE_REGION}/${BASE_BATCH} sv$(fmt6 "$SVERSION") isv$(fmt6 "$(( DIQU_VAL<<16|PLATFORM<<12|FCVER_L ))")"
for v in $VARIANTS; do
  build_variant "$v"
done
package
restore_headers
rm -rf "$LOG_DIR"
echo "全部完成。最终交付包: $ROOT/${TARGET}_firmware.zip"
