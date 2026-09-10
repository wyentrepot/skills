# DONE.md — 完成日志（需求：0003）

## 2026-09-10 完成（方案 3→1：先跑通，再自包含）

### 方案 3：全链 e2e 跑通真实工作台（`/01-workfile-ai/01-zzt/ZZT_SELF`，uvicorn :8790）
- 启动修正：`cd apps && PYTHONPATH=apps:libs .venv/bin/python -m workbench.run`（直接 `python -m` 报 `ModuleNotFoundError: shared`——shared 包在 libs/）。
- 验证链：`GET /api/health` 200 → `GET /api/ai/v2/capabilities`（zone=local_full 免 token，10 能力，module_log/listener/simcon 三源在线）→ `POST /api/ai/v2/investigations`（listener cursor_range 命中真实索引 idx-20260902-085839-f0283ef1，verdict=pass）→ `GET /jobs/{id}` 终态 → `GET /jobs/{id}/evidence?level=L1|L3`（L3 含 raw_hex + 深度解析）。
- module-action：ensure（`/dev/ttyACM0` → session ms-90a4b0fd9051/sta-main）→ send（"status"，sent=8）→ stop（409 活跃观察任务 → force:true，物理串口 fd 释放）。
- 静态校验：`tools/scripts/verify_api_inventory.py` PASS——OpenAPI 3.1.0 · 71 routes · 26 schemas · v2 task facade 8/8。

### 实测踩坑（已回填 SKILL.md「实测校准」）
1. investigation 创建信封恒 `queued`（同步历史路径也如此）——必须再 `GET /jobs/{id}` 读终态。
2. L3 evidence ref 格式 `listener:<index_id>:<frame_id>`（`index_id:frame_id` 会 422）；一次 ≤10。
3. listener 历史查询：`window.type` 仅 `cursor_range` 且 `mode` 须一致（`historic` 报 422）；需 `index_id`+`start_frame_id/end_frame_id`（索引边界内）；`match.kind` 仅 parsed_frame/frame_query。
4. token 分界：v2 local_full+loopback 免 token；v1 业务端点（listener/indexes 等）仍需 Bearer token。
5. module stop：普通 409（活跃观察任务）→ `force:true`；v2 stop job 停在 `waiting/running`（已知状态不收敛点），以物理串口释放为准。

### 方案 1：自包含改造（v2.3.0 → v2.4.0）
- 迁入：`references/operation-guide.md`（原 docs/16-AI操作指南.md，v2 默认+v1 兼容）、`references/api-contract.md`、`references/features.md`、`scripts/verify_api_inventory.py`（内置 `--repo-root`/`WORKBENCH_ROOT`/候选路径探测）。
- SKILL.md：新增「路径根解析」（references/scripts 相对技能目录；apps/docs/tools/data/.build_plain/DECISIONS 相对 `<WORKBENCH_ROOT>`）+「实测校准」；v2 表补 `jobs/{id}/cancel`；`applies-to` 修正为 `/01-workfile-ai/01-zzt/ZZT_SELF`；wsl环境部署.bat/uart-map.ps1 平台步骤条件化（仅 Windows 侧、由人执行）。
- 事实源统一：全局 `shared/hardware-in-the-loop/ai-control-plane` ↔ 仓库 `.agents/skills/ai-control-plane` 双向同步一致；陈旧 `.reasonix/skills/ai-control-plane`（v2.1.0）加 README 标注待删；README 技能表注明内容源。
- 验证：校验脚本三态（探测 PASS / 显式根 PASS / 无效根明确报错）；技能内全部路径可解析；`git diff --check` 通过（README.md 由 CRLF 规范化为 LF）；运行时副本 `/root/.dsh/skills/ai-control-plane` 同步。
