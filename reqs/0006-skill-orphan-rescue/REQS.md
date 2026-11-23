# REQS.md — 需求基线（需求 ID：0006，标题：技能孤本救援与技能存储收敛）

## 当前生效基线（版本：v1，更新：2026-11-23）

### 目标

把散落在 `~/.dsh/skills/`（实体目录）、`~/.kilo/skills/`（未跟踪）、`/mnt/d`（非 git 备份）等**不在任何版本控制里**的技能收进主仓，消除"重建软链农场即丢失"的风险；同时把两处已确认会误导人的文档与死链修掉。

### 背景（盘点结论）

全机技能分布经排查为 8 处存储、97 个不重名技能，其中 25 个是 `@volcengine/ark-cli` npm 包自带（可重生）。剔除后确认**真正只存在于单一存储且不在任何 git 里的技能共 7 个**：

| 技能 | 唯一位置 | 是否仍是现役 |
|------|----------|--------------|
| `knowledge-manage` | `~/.dsh/skills/knowledge-manage/`（实体目录） | 是（`knowledge-lookup` 的写库侧） |
| `cco-sdk-boot-swap` | `~/.dsh/skills/cco-sdk-boot-swap/`（实体目录） | 是（换 SDK / 换 boot 指导） |
| `chinese-code-review` | `~/.kilo/skills/`（git 仓内但**未被跟踪**） | 是 |
| `chinese-commit-conventions` | 同上 | 是 |
| `chinese-documentation` | 同上 | 是 |
| `embedded-function-spec` | 同上 | 是 |
| `clang-format` | `/mnt/d/doc/coding-standards-skill/uninstalled-backups/clang-format-20260728-105909/`（非 git） | 是 |

已判定**不值得救援**（已被主仓技能取代，仅记录不处理）：`parasoft-scan`（→ `fc/parasoft-static-analysis`）、`分钟采集数据分析`（→ `shared/.../mclt-collect-analysis`）、`sta-test-build` / `sta-version-build`（→ `fc/firmware-version-build`）。

### 需求点

1. **孤本入仓**：上表 7 个技能原样复制进主仓，内容零改动（md5 校验一致），按能力域归位：
   - `shared/knowledge-base/knowledge-manage/`（与 `knowledge-lookup` 同级，一读一写）
   - `fc/cco-sdk-boot-swap/`（公司 FC 环境，与 `firmware-version-build` 同域）
   - `shared/research-and-technical-expression/{chinese-code-review,chinese-commit-conventions,chinese-documentation,embedded-function-spec}/`（均为中文写作/表达规范）
   - `shared/code-quality/clang-format/`（代码格式化规范）
2. **原位改软链**：入仓后把原位置换成指向主仓的软链，与既有约定一致（`~/.dsh/skills` 是软链农场，`~/.kilo/skills` 已有 9 个软链指向主仓）。
3. **DLP 陷阱入文档**：`README.md` 的 DLP 警告补一条——E-SafeNet 加密后 `git status` 会把明文 blob 与密文工作区判成差异，**禁止在 Windows 侧对该克隆执行 `commit -a`**，否则会把密文提交进仓库。
4. **清死链**：删除本工作区 `.agents/skills/` 下 2 个指向 `deprecated/` 的死软链（`splc-flash-loop`、`splc-sync-feature`）。

### 验收标准

- [ ] 7 个技能目录在主仓内存在且内容与原位置 md5 一致。
- [ ] `~/.dsh/skills/{knowledge-manage,cco-sdk-boot-swap}` 与 `~/.kilo/skills/{chinese-*,embedded-function-spec}` 均为软链，指向主仓对应目录。
- [ ] `~/.dsh/skills`、`~/.agents/skills`、`~/.kilo/skills` 三处无失效软链。
- [ ] DSH 技能目录数量与内容在改造前后一致（`knowledge-manage`、`cco-sdk-boot-swap` 仍可见，其余不变）。
- [ ] `.agents/skills/` 下不再有指向 `deprecated/` 的条目。
- [ ] `README.md` 含 DLP 误报修改的警告；技能表补齐新增 7 个技能条目。
- [ ] `git diff --check` 通过。

### 关联代码分支（仅记录）

main（技能仓库 `/home/02-skill-fc/skills`）

## 变更记录（只追加，禁止覆盖）

### 变更 1 ｜ 2026-11-23 ｜ 用户
- **改成什么**: 执行技能盘点结论中的第 1/2/3 项——7 个孤本入仓并原位改软链、README 补 DLP 误报修改警告、清本工作区 `.agents/skills` 两个死链。
- **为什么**: 用户提问"技能数量对不上"后盘点发现 8 处存储 97 个技能，7 个只存在于单一存储且不在版本控制里，重建软链农场即永久丢失；Windows 克隆的 12 个"改动"实为 E-SafeNet 加密造成的假差异，有被误提交的风险。
- **影响**: `shared/{knowledge-base,research-and-technical-expression,code-quality}/`、`fc/`、`README.md`、`REQS-INDEX.md`、`~/.dsh/skills`、`~/.kilo/skills`、本工作区 `.agents/skills/`。
- **变更前基线**: 7 个技能仅存在于实体目录/非 git 位置（见背景表）。
- **变更后基线**: v1（全部入主仓并改软链）。
- **被取代**: 无。
