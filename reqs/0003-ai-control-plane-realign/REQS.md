# REQS.md — 需求基线（需求 ID：0003，标题：ai-control-plane 技能全局可用整改——端到端跑通 + 自包含改造）

## 当前生效基线（版本：v2，更新：2026-09-10）

> 基线 v2 说明：审核后经用户澄清，**目标是「全局可用」**——不是降级为项目作用域，而是修好路径/平台问题，让该技能在任意会话（Kilo/Reasonix/DSH）加载后都能真正操作工作台。同时确认权威仓库为 `/01-workfile-ai/01-zzt/ZZT_SELF`（v2 门面真实存在），v1 仍是专家/兼容路径。

### 目标

对全局加载的 `shared/hardware-in-the-loop/ai-control-plane`（v2.3.0，作者 reasonix）做整改，使其**全局可用**：

1. **内容与权威仓库对齐**：以 `/01-workfile-ai/01-zzt/ZZT_SELF/.agents/skills/ai-control-plane`（v2.3.0，含 v2 门面实现）为内容源，同步到全局副本（已完成，`diff -r` 一致）。
2. **先跑通（方案 3）再自包含（方案 1）**：先对真实工作台端到端验证 v2 门面（探活 → capabilities → investigation → jobs → evidence → module-action），把踩坑回填技能；再把权威参考（操作指南/接口契约/校验脚本）迁入技能自身，使技能不依赖工作台仓库位置即可解析全部路径，全局任意会话加载即用。
3. **清理平台残留与事实源分裂**：修正 `applies-to`、条件化 Windows 平台步骤、标注/删除陈旧 `.reasonix` 副本。

### 审核结论（哪里不合适）

> 更正（v2）：初版审核基于陈旧 checkout（`/mnt/d/019-wy-tool/ZZT_SELF`，v2.1.0 时代）误判「v2 门面不存在」。经用户指引权威仓库 `/01-workfile-ai/01-zzt/ZZT_SELF`（含 commit `f0e0c35 feat(ai): add v2 capability task facade`）核实：**v2 门面真实存在**（`apps/workbench/ai_v2_api.py` 含 `/api/ai/v2` 路由、`ai_capability_service.py`、`ai_contracts.py`、`tools/scripts/verify_api_inventory.py` 均在）。下述问题 1 中「内容不存在」类判定撤回；**根未声明 / 平台残留 / 事实源分裂**类问题仍成立，是「全局可用」的真正阻塞。

**证据基线**：技能全局副本 `/root/.dsh/skills/ai-control-plane/`（= 仓库 `shared/hardware-in-the-loop/ai-control-plane`，与权威仓库 `.agents/skills/ai-control-plane` v2.3.0 `diff -r` 一致）；权威仓库 `/01-workfile-ai/01-zzt/ZZT_SELF`。

#### 问题 1：路径未声明解析根 / 平台残留（原「描述错」的实情）

| # | 技能中的引用 | 实际情况 | 判定 |
|---|---|---|---|
| 1 | `docs/16-AI操作指南.md`、`docs/api-contract.md`、`docs/features.md`（SKILL.md「参考」） | 存在于权威仓库根 `docs/`，技能基目录无 docs/；技能未声明「相对工作台仓库根」 | 根未声明 → 按技能基目录解析必失败 |
| 2 | `apps/workbench/ai_v2_api.py`、`ai_capability_service.py`、`ai_contracts.py`（SKILL.md「参考」） | 存在于权威仓库 `apps/workbench/` | 内容真实；根未声明 |
| 3 | `python tools/scripts/verify_api_inventory.py`（SKILL.md「参考」） | 存在于权威仓库 `tools/scripts/` | 内容真实；根未声明 |
| 4 | metadata `applies-to: D:/2-侦听台改造` | 权威仓库在 `/01-workfile-ai/01-zzt/ZZT_SELF`（WSL）与 `D:\019-wy-tool\ZZT_SELF`（Windows 侧另有较旧副本）；`D:/2-侦听台改造` 无此目录 | 过期/错误路径 |
| 5 | 桌面 `wsl环境部署.bat` → [4]/[5]、`powershell -File uart-map.ps1 -Action start-gateway`（SKILL.md；references/listener.md） | Windows 桌面快捷方式不可移植；`uart-map.ps1` 真实位置 `tools/scripts/uart-map.ps1`（仓库相对，根未声明） | 平台路径不可移植、根未声明 |
| 6 | `D:/firmware/app.bin`（references/module-serial.md 烧录示例） | 绝对 Windows 路径，未说明是占位符 | 示例路径误导 |
| 7 | `.build_plain/apps/listener/runtime/indexes/idx-*.sqlite3`、`apps/listener/log_service.py`、`apps/workbench/orchestration/dto.py`、`apps/workbench/scenarios/profiles/`、`data/`、`tools/scripts/一键生成AI密钥.bat`（references/*） | 均为工作台仓库相对路径，技能未声明仓库根 | 根未声明 → 不可解析 |

#### 问题 2：不适合全局调用 → 实情是「全局可用」的阻塞点

1. **路径无解析根**：全局任意会话加载后，agent 无法解析 docs/apps/tools/DECISIONS 等仓库相对路径（技能只声明相对本技能目录）。
2. **事实源分裂**：权威仓库内 `.agents`（v2.3.0，权威 + 用户未提交改动）与 `.reasonix`（v2.1.0，陈旧）两份并存；全局 shared/ 需与 `.agents` 保持单一事实源。
3. **平台残留**：`wsl环境部署.bat`（桌面）、`applies-to` 过期路径、PowerShell 网关步骤——WSL/DSH 会话被误导。
4. **运行目标依赖**：操作对象是运行中的工作台（127.0.0.1:8790），需明确探活（GET /api/health）、token 获取（admin/grants 人工）、本地 full-access 前提（WORKBENCH_LOCAL_FULL_ACCESS=1）。

### 需求点

1. **内容同步（已完成）**：全局副本 = 权威仓库 `.agents/skills/ai-control-plane`（v2.3.0，含 v2 实现行改动），`diff -r` 一致；运行时副本 `/root/.dsh/skills/ai-control-plane` 同步。
2. **方案 3：先端到端跑通真实工作台**（当前阶段）：
   - 探活 `GET /api/health` → `GET /api/ai/v2/capabilities` 发现能力；
   - 提交最小 investigation / module-action → `GET /api/ai/v2/jobs/{id}` → evidence（L1→L2/L3）；
   - 记录每一步真实请求/响应、错误码与踩坑，作为技能内容校准依据。
3. **方案 1：自包含改造**（跑通后）：
   - 把权威参考迁入技能自身：`docs/16-AI操作指南.md` 相关章节 → `references/`；`docs/api-contract.md` → `references/`；`tools/scripts/verify_api_inventory.py` → `scripts/`；
   - SKILL.md 内仓库相对路径改写为技能内路径（references/、scripts/）；确需指向仓库源码/决策的（apps/workbench/*、DECISIONS.md）改为「可选深读，先向用户确认 `<WORKBENCH_ROOT>`」；
   - SKILL.md 开头声明路径根规则与候选仓库路径列表（按存在性探测）。
4. **清理与事实源统一**：修正 `applies-to` 为权威路径；`wsl环境部署.bat`/PowerShell 步骤条件化（仅 Windows 侧、由人执行）；标注/删除陈旧 `.reasonix` 副本；明确 shared ↔ 权威仓库的同步方向。

### 验收标准

- [ ] 对真实工作台端到端跑通：health → capabilities → investigation → jobs → evidence 全链成功，module-action 验证成功；踩坑已回填技能。
- [ ] 技能自包含：references/、scripts/ 内含可解析的权威参考与校验脚本，SKILL.md 无「按技能基目录解析即失败」的仓库相对路径。
- [ ] 全局任意会话加载技能后，不依赖工作台仓库位置即可完成路径解析与脚本校验（verify_api_inventory.py 可运行，只构造惰性 stub）。
- [ ] `applies-to` 修正；Windows 平台步骤条件化；陈旧 `.reasonix` 副本已标注/删除。
- [ ] 事实源统一（权威仓库 `.agents` ↔ 全局 shared/）；README / REQS-INDEX 反映新状态；`git diff --check` 通过。

### 关联代码分支（仅记录）

- 技能仓库 main（/home/02-skill-fc/skills）
- 工作台仓库 master（/01-workfile-ai/01-zzt/ZZT_SELF，权威；/mnt/d/019-wy-tool/ZZT_SELF 为较旧副本）

## 变更记录（只追加，禁止覆盖）

### 变更 2 ｜ 2026-09-10 ｜ 用户
- **改成什么**: 方向修正——目标是**全局可用**（修好路径/平台问题，让技能在任意会话可真正操作工作台），不是降级为项目作用域；并确认真实权威仓库为 `/01-workfile-ai/01-zzt/ZZT_SELF`（v2 门面真实存在）。采用「**方案 3 先端到端跑通 → 方案 1 自包含改造**」路线。
- **为什么**: 用户澄清「我们的目标是全局可用这个工作台技能」；并指出 `/01-workfile-ai/01-zzt/ZZT_SELF` 为工作台原始仓库——其中 v2 门面（f0e0c35）与 skill v2.3.0 均已落地，初版基于陈旧 checkout 的「v2 不存在」判定作废。
- **影响**: 需求点/验收标准重写（全局可用 + 自包含）；审核结论加更正注记；实现路线 = 跑通 → 自包含 → 清理。
- **变更前基线**: 基线 v1（降级为项目作用域，v1 对齐）。
- **变更后基线**: 基线 v2（全局可用，v2 门面保留为默认，自包含改造）。
- **被取代**: 变更 1。

### 变更 1 ｜ 2026-09-10 ｜ 用户
- **改成什么**: 审核并整改 ai-control-plane 技能——从全局 shared/ 降级为工作台项目作用域，内容与真实仓库（v1 接口、真实路径）对齐。
- **为什么**: （初版判断）技能全局副本 v2.3.0 大量路径描述错误/不可解析，且项目专属技能被提升到全局加载，每会话空耗并可能误触发。此条方向已被变更 2 取代。
- **影响**: 详见变更 2（本条为初版记录，保留以完整呈现演进）。
- **变更前基线**: 全局副本 v2.3.0 + 工作台项目副本 v2.1.0，事实源分裂。
- **变更后基线**: 见变更 2。
- **被取代**: 变更 2 取代本条。

### 变更 3 ｜ 2026-09-10 ｜ AI 执行（用户选定方案 3→1）
- **改成什么**: 方案 3 全链 e2e 跑通真实工作台并回填踩坑；方案 1 自包含改造完成——技能升 v2.4.0。
- **为什么**: 用户选定「先跑通（3）再自包含（1）」；工作台在 `/01-workfile-ai/01-zzt/ZZT_SELF` 启动（PYTHONPATH=apps:libs）后，v2 门面全链验证通过。
- **影响**:
  - e2e 验证：health → capabilities → investigations → jobs → evidence(L1/L3) → module ensure/send/stop 全通；`verify_api_inventory.py` PASS（v2 8/8 路由）。
  - 踩坑回填 SKILL.md「实测校准」：investigation 信封恒 queued 需读终态；L3 ref 格式 `listener:index:frame`；listener window 仅 cursor_range（mode 须一致、需 index_id+start/end_frame_id、match.kind 限 parsed_frame/frame_query）；v1 业务端点需 token 而 v2 local_full 免 token；module stop 409→force、v2 stop job 停在 waiting 属已知状态不收敛点；启动需 PYTHONPATH=apps:libs。
  - 自包含：`references/{operation-guide,api-contract,features}.md` + `scripts/verify_api_inventory.py`（内置 WORKBENCH_ROOT 解析）迁入技能；SKILL.md 加「路径根解析」；`applies-to` 修正；wsl环境部署.bat/uart-map.ps1 平台步骤条件化。
  - 事实源统一：全局 shared/ ↔ 仓库 `.agents/skills/ai-control-plane` 双向同步一致（v2.4.0）；陈旧 `.reasonix` 副本（v2.1.0）加 README 标注。
- **变更前基线**: 基线 v2 + 全局副本 v2.3.0（与 .agents 一致）。
- **变更后基线**: 全局副本 v2.4.0（自包含、路径可解析、实测校准），与 .agents 一致。
- **被取代**: 无（在变更 2 方向下落地）。
