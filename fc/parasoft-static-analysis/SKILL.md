---
name: parasoft-static-analysis
description: 仅当用户明确提到“Parasoft”、"C++test"、"cpptest"或指定 Parasoft 扫描/报告时加载。用于 C/C++ Parasoft 扫描、按 Git 提交新增行或报告基线筛选问题，以及严重等级汇总。不要用于泛化静态分析、编译或代码审查请求。
---

# Parasoft 静态扫描与提交问题筛选

## 加载边界（必须遵守）

**仅在用户明确说出 `Parasoft`、`C++test`、`cpptest`，或明确要求处理 Parasoft 扫描/`report.xml` 时加载本技能。**

以下请求不得因语义相近而加载本技能：泛泛的“静态扫描/代码检查”、编译、单元测试、代码审查、MISRA 规则解释，除非用户进一步明确指定使用 Parasoft。用户仅提及 Git 提交、严重等级或“新增问题”也不足以触发本技能。

## 先确认输入

向用户确认或从环境识别以下参数：

- **产品仓库**：必须是包含目标 Git 提交的仓库，而非 Parasoft 工具仓库。
- **待分析提交**：单提交使用 `<commit>`，提交新增行范围是 `<commit>^..<commit>`。
- **构建目标**：例如 STA 工程的 `sta_venus2m`；应选择能覆盖目标代码的产品/地区配置。
- **规则配置**：默认 `Friendcom-107.properties`。除非用户指定，不随意替换。
- **筛选条件**：严重等级（默认 1、2）、是否仅该提交新增行、是否与基线报告比较新增问题。

不要把工作区当前未提交的改动混入“某提交”结论。若目标提交不是当前 `HEAD`，优先使用干净 worktree 检出该提交再构建扫描。

## 工具位置与常规扫描

默认环境：

```bash
PARASOFT_HOME=/home/parasoft_tool/project-parasoft
CPPTEST_HOME=/home/parasoft/cpptest
PRODUCT_REPO=/path/to/product
```

常规执行器会执行 `make clean`、经 `cpptesttrace` 生成 BDF、再执行 `cpptestcli`：

```bash
cd "$PARASOFT_HOME"
./run_cpptest.sh --splc-root "$PRODUCT_REPO" -t sta_venus2m
```

扫描会重建产品并产生固件/构建产物；开始前查看 `git status --short`，不要清理或覆盖用户已有变更。

### 只读工具目录或 Eclipse configuration 不可写时

工具仓库不可写时，生成物、范围文件和 Eclipse configuration 必须改放 `/tmp`（或其他可写工作目录）。`run_cpptest.sh` 当前未传递 `-configuration`，因此先用它生成 BDF，随后手动调用 CLI：

```bash
RUN_ID="parasoft_$(date +%Y%m%d_%H%M%S)"
OUT="/tmp/$RUN_ID"
mkdir -p "$OUT/scope" "$OUT/eclipse"
: >"$OUT/scope/include.lst"; : >"$OUT/scope/exclude.lst"

cd "$PARASOFT_HOME"
PARASOFT_GEN_DIR="$OUT" \
PARASOFT_INCLUDE_LST_SRC="$OUT/scope/include.lst" \
PARASOFT_EXCLUDE_LST_SRC="$OUT/scope/exclude.lst" \
./run_cpptest.sh --splc-root "$PRODUCT_REPO" -t sta_venus2m

# 若上一步仅因 configuration 目录不可写而在 cpptestcli 阶段失败，复用已生成 BDF：
"$CPPTEST_HOME/cpptestcli" -configuration "$OUT/eclipse" \
  -data "$OUT/workspace" -settings "$PARASOFT_HOME/settings_gcc.lst" \
  -include "$OUT/include.lst" -exclude "$OUT/exclude.lst" \
  -config "$PARASOFT_HOME/Friendcom-107.properties" \
  -bdf "$OUT/product.bdf" -report "$OUT/Report" -appconsole stdout
```

空的 `include.lst` 表示纳入整个产品根；扫描大型工程耗时较长。不要因 CLI 表面等待而重复启动扫描。完成标志是日志中的 `successfully finished` 和 `Report/report.xml`。

## 快速筛选与汇总

使用本技能脚本读取 `report.xml`；脚本不会重新扫描：

```bash
SKILL=/home/02-skill-fc/skills/fc/parasoft-static-analysis
REPORT=/tmp/parasoft_xxx/Report/report.xml
```

### 1. 单个提交：仅列该提交新增/修改行的 1～2 级问题

```bash
python3 "$SKILL/scripts/parasoft_report.py" \
  --report "$REPORT" --repo "$PRODUCT_REPO" --commit <commit> --levels 1,2
```

输出先给出：完整报告各等级数量、提交新增行范围各等级数量、表格列出数量；随后是 Markdown 问题表。新增文件的所有行也会纳入。删除行没有可报告的当前代码，因此不会列出。

### 2. 指定严重等级或列出全部等级

```bash
# 仅严重等级 1
python3 "$SKILL/scripts/parasoft_report.py" --report "$REPORT" --repo "$PRODUCT_REPO" --levels 1

# 列出 1～5 级
python3 "$SKILL/scripts/parasoft_report.py" --report "$REPORT" --repo "$PRODUCT_REPO" --levels 1,2,3,4,5
```

不传 `--commit` 时，表格范围为整个报告；仍会显示每个实际出现的严重等级总量。

### 3. 对比两次扫描，只看新增问题

基线报告必须来自**相同产品、相同构建目标和相同规则配置**：

```bash
python3 "$SKILL/scripts/parasoft_report.py" \
  --report /path/to/current/Report/report.xml \
  --baseline /path/to/baseline/Report/report.xml --new-only \
  --repo "$PRODUCT_REPO" --levels 1,2
```

### 4. 同时限定“某提交新增行”与“相对基线新增”

```bash
python3 "$SKILL/scripts/parasoft_report.py" \
  --report "$REPORT" --baseline /path/to/baseline/report.xml --new-only \
  --repo "$PRODUCT_REPO" --commit <commit> --levels 1,2
```

基线匹配键为 `文件 + 规则 + 消息`，故同一既有问题仅因前方增删行而行号变化时，不会误算为新增。规则消息本身变化或文件移动会视为新增，应在结论中说明该限制。

## 输出结论规范

1. 明确扫描的提交、构建目标、规则配置、报告路径和筛选口径。
2. 必须先展示严重等级总数，再展示符合条件的问题表。
3. 没有匹配项时明确写“严重等级 N：0 项”，不要只给空表。
4. “提交问题”只陈述位于该提交**新增行**的违规；跨文件数据流或既存行的影响需另行注明，不能假称被此筛选覆盖。
5. 扫描失败、BDF 中无编译命令、`Files Checked: 0` 或报告不完整时，停止并报告失败，不输出“无问题”的结论。
