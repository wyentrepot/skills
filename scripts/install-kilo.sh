#!/usr/bin/env bash
# ============================================================================
# install-kilo.sh — 将 skills 仓库中的技能安装到 Kilo 环境
#
# 使用方式：
#   1. 在 WSL 中 clone 仓库到任意位置，例如：
#      git clone git@github.com:wyentrepot/skills.git ~/skills
#   2. 运行此脚本：
#      bash ~/skills/scripts/install-kilo.sh
#
# 作用：
#   将 shared/ 和 kilo/ 下的所有技能目录软链接到 ~/.kilo/skills/
#   Kilo 启动时自动加载 ~/.kilo/skills/ 下的技能。
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KILO_SKILLS_DIR="$HOME/.kilo/skills"
LINKED=0
SKIPPED=0
ERRORS=0

# 需要链接的技能源目录
SOURCE_DIRS=("shared" "kilo")

echo "==> 技能仓库: $REPO_DIR"
echo "==> Kilo skills: $KILO_SKILLS_DIR"

# 确保 ~/.kilo/skills 存在
mkdir -p "$KILO_SKILLS_DIR"

for src_dir in "${SOURCE_DIRS[@]}"; do
    full_src="$REPO_DIR/$src_dir"
    if [ ! -d "$full_src" ]; then
        echo "  [跳过] 源目录不存在: $full_src"
        continue
    fi

    for skill_dir in "$full_src"/*/; do
        # 跳过非目录（如 README.md）
        [ -d "$skill_dir" ] || continue

        skill_name="$(basename "$skill_dir")"
        target="$KILO_SKILLS_DIR/$skill_name"

        if [ -L "$target" ] || [ -d "$target" ]; then
            existing="$(readlink -f "$target" 2>/dev/null || echo "$target")"
            expected="$(cd "$skill_dir" && pwd)"
            if [ "$existing" = "$expected" ]; then
                echo "  [跳过] 已存在且指向正确: $skill_name"
                SKIPPED=$((SKIPPED + 1))
                continue
            else
                echo "  [跳过] 已存在但指向不同位置: $skill_name"
                echo "         现有: $existing"
                echo "         期望: $expected"
                SKIPPED=$((SKIPPED + 1))
                continue
            fi
        fi

        ln -s "$skill_dir" "$target"
        echo "  [链接] $skill_name → $target"
        LINKED=$((LINKED + 1))
    done
done

echo ""
echo "==> 完成: 新建 $LINKED 个链接, 跳过 $SKIPPED 个, 错误 $ERRORS"
echo "==> Kilo 技能目录: $KILO_SKILLS_DIR"