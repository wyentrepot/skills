# TODO.md — 交付/阶段状态（需求：0003）

## 阶段 0：前置（完成）
- [x] 内容同步：全局副本 = 权威仓库 `.agents/skills/ai-control-plane`（v2.3.0，diff -r 一致）。
- [x] 静态校验：verify_api_inventory.py PASS（v2 门面 8/8 路由）；SKILL.md v2 路由表与真实接口一致。
- [x] REQS.md 基线 v2（全局可用方向）、PLAN.md（方案 3→1）已生成。

## 阶段 3：端到端跑通真实工作台（方案 3，完成）
- [x] P3.0 启动工作台（PYTHONPATH=apps:libs，:8790）并探活 GET /api/health 200。
- [x] P3.2 发现能力 GET /api/ai/v2/capabilities（zone=local_full，10 能力，三源在线）。
- [x] P3.3-P3.5 最小只读 investigation（listener cursor_range 命中真实索引）→ jobs/{id}（verdict=pass）→ evidence L1/L3。
- [x] P3.6 module-action：ensure（ms-…/sta-main）→ send（status，sent=8）→ stop（409→force，物理口释放）。
- [x] P3.7 踩坑回填 SKILL.md「实测校准」+ module-serial/listener 条件化。

## 阶段 1：自包含改造（方案 1，完成）
- [x] P1.1 迁入 references/{operation-guide,api-contract,features}.md + scripts/verify_api_inventory.py（内置 WORKBENCH_ROOT 解析）。
- [x] P1.2 SKILL.md「路径根解析」+ 参考区改技能内路径 + v2.4.0。
- [x] P1.3 applies-to 修正；wsl环境部署.bat/uart-map.ps1 条件化。
- [x] P1.4 事实源统一：shared ↔ 仓库 .agents 双向一致；陈旧 .reasonix 副本 README 标注；README 技能表注明内容源。

## 阶段 4：验证与收尾（完成）
- [x] 校验脚本三态验证（探测 PASS / --repo-root PASS / 无效根报错）；技能内路径全部可解析；git diff --check 通过；运行时副本同步。
- [x] REQS-INDEX 状态更新、TODO/DONE 收尾、git commit。
