# 已知缺口（G1–G5）

> 拆自 wb-base/SKILL.md（2026-11-18 拆薄）。历史留档与审计用，AI 日常任务用不到。

| # | 缺口 | 位置 | 影响 | 现状/绕法 |
| --- | --- | --- | --- | --- |
| G1 | `refreshFrames` 空结果分支 `var body` 声明在使用之后（var 提升为 undefined），`body.querySelector` 抛 TypeError 被静默 `.catch` 吞掉 | `apps/workbench/static/pages/simcon/simcon.js:271-277` | 空会话/过滤无结果时列表停在"加载中…" | **2026-08-31 已修复**（`var body` 上移），留作审核记录 |
| G2 | 保活 iframe 切主题不实时跟随：外壳 `switchTheme` 对所有 iframe `postMessage({type:"wb-theme-change"})`，但只有 module-serial/maintenance/serial-profile 三页装了监听 | `pages/trace\|dict\|scenario\|simcon`、`pages/listener/index.html`、`workbench.html` | 已打开页签保持旧主题直到重载 | **2026-08-31 已修复**（六页补监听，9 个保活子页全部跟随） |
| G3 | `join_anhui` / `open_close` / `search_meter` 三个场景 `tasks/*.json` 缺失 | 编排场景模板 | `GET /api/scenarios/{id}/task` 404 明确报错，页面红条提示 | 端点行为正确，缺的是模板文件；换可用场景 |
| G4 | 侦听台依赖 C# DLL/pythonnet，缺失时挂载降级；`parse_backend=none` 时缺解析字段 | workbench 挂载层 / 侦听台解析后端 | `listener_mounted=false`、`/parse` 降级 503、`parse_unavailable` | 采帧与索引照用，不把未解析帧归入业务分类；要字段就起 Windows 解析网关（仅人执行，§6.1） |
| G5 | `.md` 路由表不被库存脚本校验 | `verify_api_inventory.py` | 只校验 v2 8 条路由命名 schema、AI 能力映射、listener schema 能力位 | 改接口时按 §6.3 第 1 条人工同步文档并跑契约测试 |

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/features.md；ai-control-plane/references/operation-guide.md

