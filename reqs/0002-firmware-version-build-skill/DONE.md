# DONE.md — 完成日志（需求：0002）

## 2026-09-10 完成
- `shared/hardware-in-the-loop/sta-version-build` 重构为 **firmware-version-build**（逐层加载）：入口 `SKILL.md`（任务→分层速查 + 10 条跨层红线）+ `references/{cco,sta,unit-test}.md`。
- 新增 `references/cco.md`：CCO/ECU（make cco / make ecu）版本编译打包全流程（版本宏表、bin2all.sh 命名、正式版/测试版交付），并入本次实测踩坑（map.sh 权限、-j8 干净构建竞态、备份-修改-恢复、归档防 clean 误删、/tmp 不可靠、版本字段歧义先确认）。
- `references/sta.md`：迁移原 sta-version-build 主体（TARGET 矩阵、基线/大同小异/小同大异、bin2dat 命名、归档与最终打包）；按实测修正 FC_SVERSION 公式（补 `PLATFORM<<12`）、移除当前分支不存在的 `sta_venus2m_v7_hrf`/`sta_venus2m_shanxi_liang_ce` 目标并加确认提示。
- `references/unit-test.md`：STA `BSPMAKE_OK=1 ... test-create` 单元测试固件编译（标注分支依赖，修正 8E1 校验位、nm `image_*` 通配符）+ 无 test-create 分支的 CCO 式手工集成替代方案 + CCO `test/Makefile` 硬件平台 unity；删除 `kilo/sta-test-build`。
- 更新 `README.md` 技能表、`REQS-INDEX.md`；`/root/.dsh/skills` 软链切换为 `firmware-version-build`。
- 验证：skill 工具可加载新技能；子代理对照真实仓库（/home/H_CCO/001/cco、/home/H_STA/04/sta）逐项核验并修正 5 处不一致；`git diff --check` 通过；无关工作树改动（codex/、dsh/、kilo/sta-auto-status-json、ai-control-plane）未暂存未提交。
