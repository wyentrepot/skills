#!/usr/bin/env bash
# ============================================================================
# install-dsh.sh — 将 skills 仓库中的 dsh/ 技能安装到 DeepSeek Harness (DSH)
#
# 使用方式：
#   1. 在 Windows (Git Bash) 或 WSL 中 clone 仓库：
#      git clone git@github.com:wyentrepot/skills.git C:/path/to/skills
#   2. 运行此脚本：
#      bash C:/path/to/skills/scripts/install-dsh.sh
#      # 或指定 DSH_HOME（默认自动探测桌面版路径）
#      DSH_HOME="C:/Users/xxx/AppData/Roaming/dsh-desktop/harness" bash .../install-dsh.sh
#
# 作用：
#   将 dsh/ 下的所有技能目录复制到 <DSH_HOME>/skills/（DSH 用户技能根）。
#   DSH 实时监视该目录，安装后无需重启即可在下一会话看到这些技能。
#
# 注意（公司 DLP 环境）：
#   若本机装有 E-SafeNet 等企业透明加密，避免用 git checkout 到 Windows
#   NTFS 后直接复制 —— 被加密的 .md 文件 DSH 读不了。请 clone 到 WSL
#   （ext4 不受 DLP 影响）再运行本脚本，或直接以 DSH 自身进程写入。
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$REPO_DIR/dsh"

# 解析 DSH_HOME：优先使用环境变量
if [ -z "${DSH_HOME:-}" ]; then
    if [ -n "${USERPROFILE:-}" ]; then
        # Windows / Git Bash
        DSH_HOME="${USERPROFILE}/AppData/Roaming/dsh-desktop/harness"
    elif [ -d /mnt/c/Users ]; then
        # WSL：映射到 Windows 用户目录
        win_user="$(ls -1 /mnt/c/Users 2>/dev/null | grep -v -E '^(Public|Default|All Users|desktop.ini)$' | head -1 || true)"
        if [ -n "$win_user" ]; then
            DSH_HOME="/mnt/c/Users/$win_user/AppData/Roaming/dsh-desktop/harness"
        else
            echo "  [错误] 无法自动探测 DSH_HOME，请手动设置: DSH_HOME=... $0"
            exit 1
        fi
    else
        echo "  [错误] 无法自动探测 DSH_HOME，请手动设置: DSH_HOME=... $0"
        exit 1
    fi
fi

DST_DIR="$DSH_HOME/skills"
echo "==> 技能仓库: $REPO_DIR"
echo "==> DSH 技能根: $DST_DIR"

if [ ! -d "$SRC_DIR" ]; then
    echo "  [错误] 未找到 dsh 技能目录: $SRC_DIR"
    exit 1
fi

mkdir -p "$DST_DIR"

COPIED=0
SKIPPED=0
for skill_dir in "$SRC_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name="$(basename "$skill_dir")"
    target="$DST_DIR/$skill_name"

    if [ -d "$target" ] && [ -f "$target/SKILL.md" ]; then
        # 已安装：用 diff 判断是否一致
        if diff -rq "$skill_dir" "$target" >/dev/null 2>&1; then
            echo "  [跳过] 已安装且一致: $skill_name"
            SKIPPED=$((SKIPPED + 1))
            continue
        fi
        echo "  [更新] 内容有差异，覆盖: $skill_name"
    else
        echo "  [复制] $skill_name → $target"
    fi
    cp -r "$skill_dir" "$target"
    COPIED=$((COPIED + 1))
done

echo ""
echo "==> 完成: 新建/更新 $COPIED 个技能, 跳过 $SKIPPED 个"
echo "==> 技能已就绪: $DST_DIR（DSH 下一会话即可使用，无需重启 profile）"