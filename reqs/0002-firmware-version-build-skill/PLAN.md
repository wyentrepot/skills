# PLAN.md — 当前执行计划（需求：0002）

- **依据需求基线版本**: v1
- **计划状态**: 当前
- **最近更新**: 2026-09-10

## 目标、架构与环境约束

将技能仓库 `shared/hardware-in-the-loop/sta-version-build` 改名并重构为分层技能 `firmware-version-build`（入口 SKILL.md + references/{cco,sta,unit-test}.md），覆盖 CCO/ECU、STA、单元测试三类编译打包；删除 `kilo/sta-test-build`。技能仓库 `/home/02-skill-fc/skills` 在沙箱中需 danger-full-access 才能写入；无关工作树改动（dsh/ 迁移、kilo/sta-auto-status-json、ai-control-plane 修改等）不得暂存或提交。

## 执行步骤

- [x] 登记 REQS-0002：创建 reqs/0002-firmware-version-build-skill/{REQS.md,PLAN.md,TODO.md}，更新 REQS-INDEX.md。
- [ ] `git mv` 重命名技能目录；`git rm kilo/sta-test-build`；更新 /root/.dsh/skills 软链（删 sta-version-build、加 firmware-version-build）。
- [ ] 重写 SKILL.md 入口（触发式 description + 任务→分层速查 + 通用红线）。
- [ ] 新增 references/cco.md（CCO/ECU 层，含本次实测经验）。
- [ ] 新增 references/sta.md（迁移原 sta-version-build 主体）。
- [ ] 新增 references/unit-test.md（STA test-create + CCO test/Makefile）。
- [ ] 更新 README.md 技能表、REQS-INDEX.md。
- [ ] 验证：skill 工具加载 firmware-version-build；references 交叉引用一致；git diff --check；子代理按技能演练 cco 流程确认可执行。
- [ ] 更新 TODO.md 勾选、写 DONE.md、REQS-INDEX 状态置已完成；git commit（仅本次改动）。

## 依赖、风险与回滚

- 依赖：技能仓库写入需沙箱提权（danger-full-access）；/root/.dsh/skills 软链可更新。
- 风险：改名可能影响引用旧名 `sta-version-build` 的文档/脚本；通过全局 grep 复核。
- 回滚：未提交前可用 git 恢复（git reset + 还原软链）；提交后可 revert 本次 commit。
