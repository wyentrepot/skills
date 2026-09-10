# PLAN.md — 实施计划（需求：0003，基线 v2，方案 3→1）

> 依据 `reqs/0003-ai-control-plane-realign/REQS.md` 基线 v2。目标：让 `ai-control-plane` 技能**全局可用**——先对真实工作台端到端跑通（方案 3），再自包含改造（方案 1）。
> 权威仓库：`/01-workfile-ai/01-zzt/ZZT_SELF`（master）。技能全局副本：`shared/hardware-in-the-loop/ai-control-plane`（= 权威仓库 `.agents/skills/ai-control-plane` v2.3.0，已 `diff -r` 一致）。

## 环境约束

- 工作台启动：`cd <WORKBENCH_ROOT>/apps && <root>/.venv/bin/python -m workbench.run`（默认端口 8790；Linux 下会枚举/补建 `/dev/ttyACM*|ttyUSB*|ttyXRUSB*` 串口节点）。
- 免 token 前提：本机 loopback + `WORKBENCH_LOCAL_FULL_ACCESS=1` → v2 全能力；否则需人工 `admin/grants` 签发 `Authorization: Bearer <token>`。
- 串口/烧录/验证类操作需要真实硬件与串口会话，只读观察（investigations/jobs/evidence）无需硬件。

## 阶段 0：前置（已完成）

- [x] 内容同步：全局副本 = 权威仓库 `.agents/skills/ai-control-plane`（`diff -r` 一致）；运行时副本 `/root/.dsh/skills/ai-control-plane` 同步。
- [x] 静态校验：`verify_api_inventory.py` PASS——OpenAPI 3.1.0 · 71 routes · 26 schemas · v2 task facade 8/8（capabilities / investigations / verification-runs / module-actions / flash-jobs / jobs/{id} / jobs/{id}/cancel / jobs/{id}/evidence）。SKILL.md v2 路由表与真实接口一致；唯一缺口：SKILL.md 未提 `POST /api/ai/v2/jobs/{job_id}/cancel`（计划 P3 阶段补齐）。

## 阶段 3：端到端跑通真实工作台（需工作台在线）

> 前置失败检查：`curl -s -m 5 http://127.0.0.1:8790/api/health`。当前为 `HTTP 000`（未运行）→ 需先启动（人工或本计划 P3.0）。

- [ ] **P3.0 启动工作台**：`cd /01-workfile-ai/01-zzt/ZZT_SELF/apps && ../.venv/bin/python -m workbench.run`（后台 job，port 8790）。启动前确认无已有实例、串口无冲突。
- [ ] **P3.1 探活**：`curl -s http://127.0.0.1:8790/api/health` → 期望 200 + `{"status":"ok"}` 类。
- [ ] **P3.2 发现能力**：`GET /api/ai/v2/capabilities` → 期望 CapabilitySnapshot（含 10 个 capability + sources + scopes，与静态清单一致）。
- [ ] **P3.3 最小只读 investigation**：`POST /api/ai/v2/investigations`（带 `client_request_id`，观察类型取 listener 分钟采集或 module_log 窗口，仅只读）→ 期望 202 + `job_id`。
- [ ] **P3.4 读 job**：`GET /api/ai/v2/jobs/{job_id}` 轮询至 `job_state` 终态（成功/失败/超时）。
- [ ] **P3.5 取证分级**：`GET /api/ai/v2/jobs/{job_id}/evidence?level=L1` → 摘要；按需 `level=L2|L3`。
- [ ] **P3.6 module-action（可选，需串口）**：`POST /api/ai/v2/module-actions` action=ensure → send → stop；若 409（串口占用/会话冲突）则等待或换口，不硬抢。此步需用户确认有可用 cco/sta 串口硬件，否则跳过并记录。
- [ ] **P3.7 踩坑回填**：将真实请求/响应/错误码与技能描述差异（含 cancel 路由缺失、token/端口/串口前提、evidence level 行为）回填 SKILL.md / references；确认 / 修正 `applies-to`。

### 阶段 3 验收

- [ ] health → capabilities → investigation → jobs → evidence 全链成功；module-action 成功或明确记录「无串口硬件跳过」。
- [ ] 回填后的 SKILL.md 无与真实接口矛盾的路径/端点/前提。

## 阶段 1：自包含改造（跑通后）

- [ ] **P1.1 参考文档迁入技能**：
  - `docs/16-AI操作指南.md` → `references/operation-guide.md`（权威操作手册，或按需节选）。
  - `docs/api-contract.md` → `references/api-contract.md`（接口契约总表）。
  - `tools/scripts/verify_api_inventory.py` → `scripts/verify_api_inventory.py`，**适配**：`REPO_ROOT` 改为优先读 `WORKBENCH_ROOT` 环境变量 / `--repo-root`，缺失时探测候选路径（`/01-workfile-ai/01-zzt/ZZT_SELF`、`/mnt/d/019-wy-tool/ZZT_SELF`、`D:\019-wy-tool\ZZT_SELF`）；找不到仓库时明确报错并提示设置 `WORKBENCH_ROOT`。
- [ ] **P1.2 SKILL.md 路径根声明**：开头写明「`references/`、`scripts/` 相对本技能目录；`apps/`、`docs/`、`tools/`、`data/`、`.build_plain/`、`DECISIONS.md` 相对工作台仓库根 `<WORKBENCH_ROOT>`（候选路径见下，按存在性探测）」。参考区改为技能内路径 + 仓库脚本深读说明。
- [ ] **P1.3 平台残留清理**：`applies-to` 修正为 `/01-workfile-ai/01-zzt/ZZT_SELF`（WSL 权威）/ `D:\019-wy-tool\ZZT_SELF`（Windows）；`桌面 wsl环境部署.bat`、`powershell -File uart-map.ps1` 改为条件式（仅 Windows 侧、由人执行，真实相对路径 `tools/scripts/uart-map.ps1`）；`D:/firmware/app.bin` 示例标注「占位符，按实际路径替换」。
- [ ] **P1.4 事实源统一**：权威仓库 `.reasonix/skills/ai-control-plane`（v2.1.0 陈旧）标注「陈旧，以 .agents 副本为准」或删除（由用户定）；README 技能表 ai-control-plane 行注明「全局技能，内容源=权威仓库 .agents 副本」。
- [ ] **P1.5 验证**：
  - `python scripts/verify_api_inventory.py`（于仓库根或 `WORKBENCH_ROOT` 指定时）→ PASS。
  - 技能内所有 `references/`、`scripts/` 路径存在；SKILL.md 无「按技能基目录解析即失败」的仓库相对路径。
  - `/root/.dsh/skills/ai-control-plane` 运行时副本同步；`skill` 工具可加载。
  - `git diff --check` 通过。

### 阶段 1 验收

- [ ] 全局任意会话加载技能后，不依赖工作台仓库位置即可解析全部技能内路径；校验脚本可运行（惰性 stub，不开串口/不启动侦听台/不烧录）。
- [ ] `applies-to` 修正、平台步骤条件化、陈旧副本已标注/删除、README/REQS-INDEX 更新。

## 收尾

- [ ] `REQS-INDEX.md` 状态 → ✅ 已完成；`TODO.md` 勾选全部；`DONE.md` 追加完成日志。
- [ ] 提交：技能仓库（shared/、reqs/0003/、README、REQS-INDEX）`git commit`；工作台仓库（若改 `.agents` 副本/`applies-to`）按需提交。

## 回滚与失败处理

- 工作台启动失败：检查 `.venv`、端口占用（`lsof -i:8790`）、缺依赖；回退为「静态校验 + 文档对齐」，向用户报告阻塞。
- module-action 409：按技能红线等待/换口/跳过，不硬抢、不并发重试。
- 自包含脚本迁移后若 `REPO_ROOT` 探测失败：确认 `WORKBENCH_ROOT` 设置或候选路径存在；必要时回退为「文档说明指向仓库脚本」，不强行复制。
