# TODO.md — 0006 技能孤本救援与技能存储收敛

## 阶段 1：孤本入仓

- [x] 复制 7 个技能进主仓对应分区，md5 校验与原位置一致
- [x] 原位替换为软链（`~/.dsh/skills` ×2、`~/.kilo/skills` ×4）
- [x] 校验三处技能根无失效软链

## 阶段 2：文档修订

- [x] `README.md` 补 DLP 误报修改警告
- [x] `README.md` 技能表补齐 7 个技能条目
- [x] `REQS-INDEX.md` 登记本需求

## 阶段 3：清理

- [x] 删本工作区 `.agents/skills/` 两个指向 `deprecated/` 的死软链
- [x] 全量校验 + 提交（`dd0c31f`）
