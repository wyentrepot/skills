# MCP（暂空）

当前状态：**暂未接入**。

- 没有 MCP 工具表；AI 通过 `$SKILL_DIR/scripts/fcctl.py` CLI 调用 8765；
- 不要假设存在 MCP server 或工具名；
- commit 在 MCP 薄层也存在（`fc_upgrade_commit`），但只在用户明确授权后调用、必须带 `user_approval`；本技能默认走 CLI `flash-commit`，不依赖 MCP。

等明确要做 MCP 薄层时，在此补充工具映射。
