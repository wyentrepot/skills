# 单元测试固件编译（STA / CCO）

## STA：Unity 单元测试固件

> **⚠ 机制是分支相关的**：`BSPMAKE_OK=1 ... test-create` / `unity_runner.py` / `-DUNITY_TEST_FUNC` 机制存在于历史提交 4a5b536f 及其分支（如 `anhui_develop_26-1`、`fix/version_manage`）；**当前默认检出分支（如 `hebei_develop`）已无此机制**。动工前先确认所在分支含该机制；否则按下方「无 test-create 分支的替代方案」走 CCO 式手工集成。

- 仓库：`/home/H_STA/04/sta`；确认分支是否含 test-create：`grep -n "test-create\|UNITY_TEST_FUNC" Makefile`。
- runner（`*_test_runner.c`）由 `unity_runner.py` 自动生成；首次编译或新增/修改 `xxx_test.c` 后先执行：

  ```bash
  make BSPMAKE_OK=1 test-create
  ```

- 编译（V2 平台）：

  ```bash
  make BSPMAKE_OK=1 AREA=<MODE> sta_venus2m clean && \
  make BSPMAKE_OK=1 AREA=<MODE> sta_venus2m test-create -j8
  ```

  `<MODE>` 为地区宏，如 `HU_NAN_MODE`、`ZHE_JIANG_MODE`。
- **必须先 `make clean`**：`-DUNITY_TEST_FUNC` 通过 `SECOND_ARG=test-create` 传入，宏变化不会触发 .o 重编；不 clean 则 `main.c` 的 `#ifdef UNITY_TEST_FUNC` 块不会编入固件，上电无测试打印。
- 输出 `firmware/sta_venus2m/`：

  | 文件 | 说明 | 烧录地址 |
  |---|---|---|
  | `flash_sta_venus2m_*.bin` | 主固件 flash 镜像 | flash 0x5000 |
  | `flash_sta3_venus2m_*.bin` | 参数区 flash 镜像 | flash 0x0 |
  | `iap_sta_venus2m_*.bin` | IAP 引导 | IAP 分区 |
  | `upgrade_sta_venus2m_*.dat` | 远程升级文件 | — |

  ELF/map 在 `firmware/sta_venus2m/debug/`。
- 串口：`uart1`，**115200 8E1**（platform_output.c 用 `BSP_PARITY_EVEN`）；上电后 `main.c` 调 `unity_test_init()`，随后 `All_tests_main()` 经 `UNITY_OUTPUT_CHAR` 逐字符输出结果。
- `.testignore`：`unity_test/.testignore` 跳过不需要的测试组，修改后重跑 `make BSPMAKE_OK=1 test-create`。
- 验证固件包含测试：

  ```bash
  riscv64-unknown-elf-nm firmware/sta_venus2m/debug/image_* \
    | grep -iE "All_tests_main|unity_test_init|RunAllTests|UNITY_OUTPUT"
  ```

  预期输出包含上述符号地址（ELF 文件无 `.elf` 后缀，用 `image_*` 匹配）。

## 无 test-create 分支的替代方案（当前默认检出）

当前无 test-create 机制的分支上，按 CCO 同款手工集成（详见 `test/在硬件平台上使用单元测试框架.md`）：
在 `main()` 中 `extern void unity_test_init(void); unity_test_init();`，把 `alltest.c` 的 `main` 改名后在 `while(1)` 前调用，经 uart 输出测试结果；测试代码默认不参与正式构建。

## CCO：硬件平台 Unity 单测

- 仓库：`/home/H_CCO/001/cco`；框架在 `test/unity.framework`，测试目录 `test/test_bsp`、`test_components`、`test_phy`、`dev_test`、`mac_sublayer_test`、`mac_test` 等。
- 开关：`test/Makefile` 的 `obj-y`（unity.framework / mac_sublayer_test / mac_test 默认注释）。**测试代码默认不参与顶层 `make cco/ecu`**；生产版本应移除测试代码。
- 集成（详见 `test/在硬件平台上使用单元测试框架.md`）：在 `main()` 中
  `extern void unity_test_init(void); unity_test_init();`，并把 `alltest.c` 的 `main` 改名后在 `while(1)` 前调用；
  结果经与集中器交互的串口输出。
