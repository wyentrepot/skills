---
name: firmware-version-build
description: Use when 需要编译/打包 CCO、ECU 或 STA 固件（make cco / make ecu / make sta_venus2m*），包括大小版本变体、正式版/测试版双版本，或生成带 Unity 单元测试的测试固件（BSPMAKE_OK=1 ... test-create）。例如"出正式版与测试版 2 个程序"、"按大同小异/小同大异出 3 个变体"、"编译单元测试固件"。
---

# 固件版本编译打包（firmware-version-build）

## 加载模型（渐进式，唯一路径）

```
用户明确要求编译/打包/出程序？
├─ 否 ────────────────► 不加载本技能
└─ 是 ──► 第1级 按工程分派（只加载对应一层 references/，用完即止）
     ├─ CCO/ECU 固件   → references/cco.md       → 唯一执行路径: scripts/build_cco.sh
     ├─ STA 固件       → references/sta.md       → 唯一执行路径: scripts/build_variants.sh
     └─ 单元测试固件   → references/unit-test.md → 见该层
```

- **单/多编译不设两条文档流程**：由脚本输入参数决定（`build_cco.sh` 一次 `build` = 单编译、多次 `build` = 多编译；`build_variants.sh` 用 `--variants` 决定变体数量）。
- 各层内部**唯一执行路径 = 对应一键脚本**（均带仓库定位路径保护，可放任意位置运行）。手动改宏/手动 make 仅作脚本异常时的排查参照，不当作并行流程。
- 任务描述与"加载哪一层"对照（第1级分派表）：

| 触发词 | 工程 | 加载层 | 执行脚本 |
|---|---|---|---|
| make cco / make ecu / CCO固件 / ECU固件 | CCO/ECU | references/cco.md | scripts/build_cco.sh |
| make sta_venus2m* / STA固件 / 表模块 / 大同小异 / 小同大异 | STA | references/sta.md | scripts/build_variants.sh |
| test-create / Unity / 测试固件 | 单元测试 | references/unit-test.md | 见该层 |

## 通用红线（跨 cco/sta/单测）

1. **版本字段歧义先确认**：需求版本串（如 `sv2601-svdate260422-1401`）可能含误导/无关字段。
   动工前把 SVERSION / 版本日期 / isv(FC_VERSION_L) / idate(FC_VER) / 批次 / 地区逐项映射给用户确认，再编译。
2. **备份-修改-恢复**：改版本头文件前先备份；每编译完一个变体立即归档输出，再恢复头文件，变体间互不影响。
   （一键脚本已内置该闭环；手动作业时遵守。）
3. **变体编译前必须 `make clean`**：版本宏在 .h 中，不 clean 会复用旧 .o。（脚本内置。）
4. **`jump` 作第二参数**：`make {target} jump`，避免 bin2all/bin2dat 在 stdin 等待（提交次数/厂商代码）。（脚本内置。）
5. **归档放 firmware/ 之外**：`make clean` / bin2all 会清 `firmware/*`；归档目录内的 .bin/.dat 会被下次 clean 递归误删（只拷 .zip 最安全）。（脚本归档在仓库根 `archive_*`。）
6. **日期无前导零 / 用 BCD 位**：`08` 会被编译器当八进制；CCO 的 `VER_YEAR` 等是 BCD（`260916` → `0x26/0x09/0x16`）。
7. **`map.sh` 需可执行**：若 Makefile 调 `./map.sh` 而文件无 x 位，make 在最后一步报 `Permission denied`（固件已产出但退出码 2）→ `chmod +x map.sh`。
8. **干净构建 `-j8` 竞态（实测确认）**：全新构建必须串行 `make clean && make {target} jump`（实测 ~32~76s）；`-j8` 会触发 `built-in.o` 链接竞态，符号错乱、产物损坏。（脚本默认串行。）
9. **临时目录不可靠**：沙箱/CI 的 /tmp 可能在命令间清空；备份、暂存放项目内或同一条命令内完成。
10. **同名宏出现在多个地区分支**：编辑必须块作用域定位（脚本已内置，跨地区安全）；手动作业时用 DIQU_PRINTF_STRING / 日期上下文锚定唯一分支。
11. **一键脚本是唯一执行路径**：CCO/ECU → `scripts/build_cco.sh`；STA → `scripts/build_variants.sh`。两脚本均支持 `--repo`/环境变量/向上自动探测三级仓库定位 + 合法性校验（未定位到合法仓库一律拒绝执行），内置 备份→改宏→串行编译→预期 zip 名校验→归档→恢复头文件，失败自动恢复。**勿手搓机械步骤。**

## 可扩容性（新增工程/平台）

1. `references/` 新增 `<工程>.md`（含脚本调用与参数说明，顶部写清"唯一执行路径"）。
2. `scripts/` 增加对应一键脚本（复用 `build_cco.sh` / `build_variants.sh` 的仓库定位 + 块作用域改宏 + 校验归档模式）。
3. 本文件"第1级分派表"加一行。
4. 通用红线跨层共享，新层不得改旧层逻辑 —— 保证兼容不回归。

## 兼容性

- 入口层只做"触发判断 + 工程分派"，不含任何平台细节；各层自包含。
- 脚本参数向后兼容：新增参数只做增量（如 `--variants`），不改变既有调用语义。
