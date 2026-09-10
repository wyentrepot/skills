# REQS.md — 需求基线（需求 ID：0002，标题：固件版本编译打包技能整合（cco/sta/单元测试））

## 当前生效基线（版本：v1，更新：2026-09-10）

### 目标

将 `shared/hardware-in-the-loop/sta-version-build`（原 STA 大小版本编译打包技能）重构为**逐层加载**技能 `firmware-version-build`，覆盖 **CCO/ECU**、**STA**、**单元测试**三类编译打包场景，并把本次 CCO/ECU（`make ecu`）编译实测经验写入技能。

### 需求点

- 目录改名：`shared/hardware-in-the-loop/sta-version-build` → `firmware-version-build`。
- 分层结构（入口 + 按需加载的 `references/`，沿用 ai-control-plane 逐层加载模式）：
  - `SKILL.md`：入口层，任务→分层速查 + 跨层红线（精简）。
  - `references/cco.md`：CCO/ECU 编译打包层（make cco / make ecu、版本宏、bin2all.sh 命名、正式版/测试版打包、实测踩坑）。
  - `references/sta.md`：STA 编译打包层（原技能主体：TARGET 矩阵、基线/大同小异/小同大异、bin2dat 命名、归档）。
  - `references/unit-test.md`：单元测试编译层（STA `BSPMAKE_OK=1 ... test-create`；CCO `test/Makefile` 开关 + 硬件平台 unity）。
- 删除 `kilo/sta-test-build`，其内容并入 `references/unit-test.md`。
- 更新 `/root/.dsh/skills/` 软链、仓库 `README.md` 技能表、`REQS-INDEX.md`。
- description 改为触发式（"Use when ..."）且不总结工作流。

### 验收标准

- [ ] `firmware-version-build` 目录含 `SKILL.md` 与 `references/{cco,sta,unit-test}.md`，内容完整、交叉引用一致。
- [ ] `kilo/sta-test-build` 已删除，其关键内容能在 `references/unit-test.md` 找到。
- [ ] `/root/.dsh/skills/firmware-version-build` 软链有效，`skill` 工具可加载该技能。
- [ ] README 技能表、REQS-INDEX 反映 0002 与新名称。
- [ ] `git diff --check` 通过；无关工作树改动未被暂存/提交。

### 关联代码分支（仅记录）

main（技能仓库 /home/02-skill-fc/skills）

## 变更记录（只追加，禁止覆盖）

### 变更 1 ｜ 2026-09-10 ｜ 用户
- **改成什么**: 将 sta-version-build 重构为 firmware-version-build 分层技能，新增 cco/单元测试层，删除 kilo/sta-test-build。
- **为什么**: 本次 CCO/ECU（make ecu）编译暴露了原技能未覆盖的平台与踩坑（map.sh 权限、-j8 干净构建竞态、备份-修改-恢复、正式版/测试版交付、版本字段歧义先确认），需把实测经验固化并按 cco/sta/单元测试分层。
- **影响**: shared/hardware-in-the-loop/（技能改名+分层）、kilo/sta-test-build（删除）、README、REQS-INDEX、/root/.dsh/skills 软链。
- **变更前基线**: sta-version-build（单文件 SKILL.md，211 行）+ kilo/sta-test-build（独立）。
- **变更后基线**: firmware-version-build（入口 + references/ 三层）。
- **被取代**: 无。
