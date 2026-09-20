# TODO.md — 交付/阶段状态（需求：0002）

## 阶段 1：登记与重构
- [x] REQS-0002 已登记（REQS.md/PLAN.md/TODO.md + 索引）。

## 阶段 2：技能分层落地
- [x] firmware-version-build 目录 + 入口 SKILL.md + references/{cco,sta,unit-test}.md 完成；kilo/sta-test-build 已删除。

## 阶段 3：配套与验证
- [x] README/REQS-INDEX 更新，软链生效，skill 可加载，验证通过，git commit 完成。

## 阶段 4：STA 一键脚本自动化（降本）
- [x] 新增 `scripts/build_variants.sh`：基线读取(块作用域定位宏)→备份→改宏→串行编译→预期 zip 名校验→归档→恢复→最终打包，一次后台调用替代 ~15 次工具往返。
- [x] 实测验证：安徽 v7 两变体（datong_xiaoyi/xiaotong_dayi）端到端跑通，产物与手动流程一致（sv001401-260509-isv091007-idate260916 / sv001402-260916-isv091006-idate260914）。
- [x] references/sta.md 增加"一键脚本优先"小节；SKILL.md 红线 11 合并 STA 脚本指引。
- [x] 路径保护：脚本唯一权威源放技能目录 scripts/（工作区不留副本），支持 `--repo`/`$STA_REPO`/向上自动探测三级定位，未定位到合法 STA 仓库一律拒绝执行，执行前打印操作仓库。
- [x] 完整端到端复验：从中性 cwd + `--repo` 调用技能目录脚本，产物与手工一致。
- [x] CCO/ECU 补齐：`scripts/build_cco.sh`（一次 build=单编译, 多次=多编译; 参数显式传 SVERSION/VDATE/IDATE, BCD 转换, 路径保护），实测复现基线 zip `浙江-2602-CCO-sv002601-260903-isv140026-idate260916-1.zip`。
- [x] 加载模型重构（渐进式/精简/唯一路径）：SKILL.md 改为 触发条件(明确要求编译)→第1级工程分派(CCO/ECU|STA|单测)→各层唯一执行路径=脚本(单/多编译由脚本参数决定)；新增"可扩容性/兼容性"节；cco.md/sta.md 同步为"唯一执行路径"表述。
- [ ] 后续：CCO/ECU 侧 `build_fw.sh` 历史文档残留清理核对；unit-test.md 层对齐"唯一执行路径"表述。
