# 部署形态与前缀映射（最容易踩的一层）

> 拆自 wb-base/SKILL.md（2026-11-18 拆薄）。排查挂载/前缀问题、改接口时才读本文件。

### 前言：部署形态与前缀映射（最容易踩的一层）

- **入口**：统一工作台 `apps/workbench/run.py` → **8790**，`/api/*` 各命名空间，页面 `/static/pages/<页名>/`、外壳 `/`；侦听台独立版 `apps/listener/run.py` → 8765，`/api/*`（无业务段）；模块日志独立版 `apps/module_log/run.py` → 8766，`/api/module-serial/*`；simcon 独立版 `python -m sim_concentrator.api` → 8781，`/api/simcon/*`。
- **挂载代理语义**：**外部路径 = `{api_prefix}{rest}` → 子应用收到 `{sub_root}{rest}`**。`/api/listener/*` 由 listener 接、**剥业务段**（`/api/listener/logs/status` → 子应用 `/api/logs/status`）；`/api/module-serial/*`、`/api/fs/*`、`/api/loghooks/*` 由 module_log 接、同前缀透传；`/api/simcon/*` 是 simcon **平级顶层 mount**（REQS-0023，不经 module_log，无剥前缀）；`/api/ai/v1/*` 与其余 `/api/*` 由 workbench 自身接（AI 控制面 / 编排·字典·串口 Profile）；`/static/*`、`/` 走静态外壳（NoCacheHTMLStaticFiles）。
- **双前缀特例（勿"修正"）**：listener 子应用自身有 `/api/listener/*` 路由（traces、indexes），叠加挂载前缀后外部路径是 **`/api/listener/listener/traces`**（trace.js 就这么调）。indexes 同时暴露为 `/api/indexes` 与 `/api/listener/indexes`，故外部两种写法都有效。
- **挂载降级**：listener 依赖 C# DLL/pythonnet，挂载失败自动降级（`GET /api/platform-version` 里 `listener_mounted=false`，页签显示"不可用"），不拖垮整体。
- **平台端点**：`GET /`（外壳）、`GET /api/platform-version`（`{app, version, module_log_mounted, listener_mounted}`）、`GET /api/health`（`{status:"ok", app:"workbench"}`，免鉴权探活）、`POST /api/shutdown`（uvicorn graceful 停机，进程退出）。

> 来源：ai-control-plane/references/api-contract.md

