---
name: firmware-version-build
description: Use when 需要编译/打包 CCO、ECU 或 STA 固件（make cco / make ecu / make sta_venus2m*），包括大小版本变体、正式版/测试版双版本，或生成带 Unity 单元测试的测试固件（BSPMAKE_OK=1 ... test-create）。例如"出正式版与测试版 2 个程序"、"按大同小异/小同大异出 3 个变体"、"编译单元测试固件"。
---

# 固件版本编译打包（firmware-version-build）

CCO / ECU / STA 固件的版本编译、打包与归档。本文件是**入口层**：只做"选层"与通用红线；
具体平台流程按需加载对应 `references/`（逐层加载，只用该层，用完即止）。

## 任务 → 加载哪一层

| 任务 | 编译命令（项目根） | 加载 |
|---|---|---|
| CCO 模块固件 | `make cco` | references/cco.md |
| ECU 模块固件（-DECU2_BOARD） | `make ecu` | references/cco.md |
| STA 各平台固件（含 大同小异/小同大异 变体） | `make {sta_venus2m*} jump`（需进 sta/） | references/sta.md |
| 单元测试固件（STA / CCO） | `BSPMAKE_OK=1 ... test-create` / `test/Makefile` | references/unit-test.md |

## 通用红线（跨 cco/sta/单测）

1. **版本字段歧义先确认**：需求版本串（如 `sv2601-svdate260422-1401`）可能含误导/无关字段。
   动工前把 SVERSION / 版本日期 / isv(FC_VERSION_L) / idate(FC_VER) / 批次 / 地区逐项映射给用户确认，再编译。
2. **备份-修改-恢复**：改版本头文件前先备份；每编译完一个变体立即归档输出，再恢复头文件，变体间互不影响。
3. **变体编译前必须 `make clean`**：版本宏在 .h 中，不 clean 会复用旧 .o。
4. **`jump` 作第二参数**：`make {target} jump`，避免 bin2all/bin2dat 在 stdin 等待（提交次数/厂商代码）。
5. **归档放 firmware/ 之外**：`make clean` / bin2all 会清 `firmware/*`；归档目录内的 .bin/.dat 会被下次 clean 递归误删（只拷 .zip 最安全）。
6. **日期无前导零**：`08` 会被编译器当八进制；用 `8` 或 `0x08`。
7. **`map.sh` 需可执行**：若 Makefile 调 `./map.sh` 而文件无 x 位，make 在最后一步报 `Permission denied`（固件已产出但退出码 2）→ `chmod +x map.sh`。
8. **干净构建 `-j8` 竞态**：`make clean && make {target} -j8` 可能报 `No rule to make target 'built-in.o'`（all 的递归构建与链接并行）→ 全新构建用**串行** `make clean && make {target} jump`。
9. **临时目录不可靠**：沙箱/CI 的 /tmp 可能在命令间清空；备份、暂存放项目内或同一条命令内完成。
10. **同名 SVERSION 出现在多个地区分支**：编辑时必须带日期 / DIQU_PRINTF_STRING 上下文锚定唯一分支。
