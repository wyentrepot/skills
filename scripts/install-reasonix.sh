#!/usr/bin/env bash
# ============================================================================
# install-reasonix.sh — 将 skills 仓库中的技能注册到 Reasonix 环境
#
# 使用方式：
#   1. 在 Windows (Git Bash / WSL) 中 clone 仓库：
#      git clone git@github.com:wyentrepot/skills.git C:/path/to/skills
#   2. 运行此脚本自动配置：
#      bash C:/path/to/skills/scripts/install-reasonix.sh
#
# 作用：
#   将 shared/ 和 reasonix/ 路径添加到 Reasonix 的 ~/.reasonix/config.toml
#   的 [skills] paths 中。
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REASONIX_CONFIG="$HOME/.reasonix/config.toml"
SHARED_PATH="$REPO_DIR/shared"
REASONIX_PATH="$REPO_DIR/reasonix"

echo "==> 技能仓库: $REPO_DIR"
echo "==> Reasonix 配置: $REASONIX_CONFIG"

# 检查目录是否存在
if [ ! -d "$SHARED_PATH" ]; then
    echo "  [错误] 未找到 shared 目录: $SHARED_PATH"
    exit 1
fi
if [ ! -d "$REASONIX_PATH" ]; then
    echo "  [错误] 未找到 reasonix 目录: $REASONIX_PATH"
    exit 1
fi

# 确保配置目录存在
mkdir -p "$(dirname "$REASONIX_CONFIG")"

# 读取现有配置
EXISTING_PATHS=""
if [ -f "$REASONIX_CONFIG" ]; then
    # 提取现有的 [skills] paths 部分
    EXISTING_PATHS=$(grep -E '^\s*paths\s*=' "$REASONIX_CONFIG" 2>/dev/null || true)
fi

# 检查是否已配置
NEED_SHARED=true
NEED_REASONIX=true

if echo "$EXISTING_PATHS" | grep -qF "$SHARED_PATH"; then
    NEED_SHARED=false
    echo "  [跳过] shared 路径已配置"
fi
if echo "$EXISTING_PATHS" | grep -qF "$REASONIX_PATH"; then
    NEED_REASONIX=false
    echo "  [跳过] reasonix 路径已配置"
fi

if [ "$NEED_SHARED" = false ] && [ "$NEED_REASONIX" = false ]; then
    echo "==> 已完成，无需修改。"
    exit 0
fi

# 追加配置
{
    echo ""
    echo "# Skills 仓库（由 install-reasonix.sh 自动添加，参考：https://github.com/wyentrepot/skills）"
    if grep -q '^\[skills\]' "$REASONIX_CONFIG" 2>/dev/null; then
        # 已有 [skills] 段，只追加 paths
        echo "paths = ["
        if [ "$NEED_SHARED" = true ]; then
            echo "  \"$SHARED_PATH\","
        fi
        if [ "$NEED_REASONIX" = true ]; then
            echo "  \"$REASONIX_PATH\","
        fi
        echo "]"
    else
        # 新建 [skills] 段
        echo "[skills]"
        echo "paths = ["
        if [ "$NEED_SHARED" = true ]; then
            echo "  \"$SHARED_PATH\","
        fi
        if [ "$NEED_REASONIX" = true ]; then
            echo "  \"$REASONIX_PATH\","
        fi
        echo "]"
    fi
} >> "$REASONIX_CONFIG"

echo "==> 已添加到 $REASONIX_CONFIG"
echo "==> 重启 Reasonix 后技能即可生效。"
