---
name: sta-test-build
description: STA 固件 Unity 单元测试模式编译打包。生成带 -DUNITY_TEST_FUNC 的测试固件，上电后自动运行所有测试并通过 uart1 (115200) 输出结果。
---

# STA 单元测试固件编译流程

## 工作目录

```bash
cd /home/H_STA/04/sta
```

## 前置条件

测试 runner 文件（`*_test_runner.c`）由 `unity_runner.py` 自动生成。首次编译或新增/修改 `xxx_test.c` 后需先执行：

```bash
make BSPMAKE_OK=1 test-create
```

## 编译命令

### V2 平台（`sta_venus2m`）

```bash
make BSPMAKE_OK=1 AREA=<MODE> sta_venus2m clean && \
make BSPMAKE_OK=1 AREA=<MODE> sta_venus2m test-create -j8
```

`<MODE>` 替换为实际地区宏，如：`HU_NAN_MODE`、`ZHE_JIANG_MODE`、`FU_JIAN_MODE` 等。

## 关键说明

### 必须先 `make clean`

`-DUNITY_TEST_FUNC` 宏通过 Makefile 的 `SECOND_ARG=test-create` 传入。**make 不会因宏变化自动重编译已有 `.o` 文件**，必须先 `clean` 强制全量重编，否则 `main.c:222` 的 `#ifdef UNITY_TEST_FUNC` 块不会被编译进固件，导致上电无测试打印。

### 输出文件

编译成功后，烧录文件位于 `firmware/sta_venus2m/` 目录：

| 文件 | 说明 | 烧录地址 |
|------|------|---------|
| `flash_sta_venus2m_*.bin` | 主固件 flash 镜像 | flash 偏移 0x5000 |
| `flash_sta3_venus2m_*.bin` | 参数区 flash 镜像 | flash 偏移 0x0 |
| `iap_sta_venus2m_*.bin` | IAP 引导 | IAP 分区 |
| `upgrade_sta_venus2m_*.dat` | 远程升级文件 | — |

ELF 和 map 文件在 `firmware/sta_venus2m/debug/` 目录下。

### 串口参数

- 串口：`uart1`
- 波特率：**115200** 8N1
- 上电后 `main.c` 调用 `unity_test_init()` 初始化 UART，随后 `All_tests_main()` 执行所有测试并通过 `UNITY_OUTPUT_CHAR` 逐字符输出结果

## `.testignore` 使用

`unity_test/.testignore` 可跳过不需要的测试组，修改后重新执行 `make BSPMAKE_OK=1 test-create` 即可生效。

## 验证固件包含测试

编译后检查 ELF 中是否有测试符号：

```bash
riscv64-unknown-elf-nm firmware/sta_venus2m/debug/image_*.elf \
  | grep -iE "All_tests_main|unity_test_init|RunAllTests|UNITY_OUTPUT"
```

预期输出包含上述符号的地址。

## 完整示例（湖南）

```bash
# 1. 生成测试 runner
make BSPMAKE_OK=1 test-create

# 2. 编译测试固件
make BSPMAKE_OK=1 AREA=HU_NAN_MODE sta_venus2m clean && \
make BSPMAKE_OK=1 AREA=HU_NAN_MODE sta_venus2m test-create -j8

# 3. 烧录 firmware/sta_venus2m/flash_sta_venus2m_*.bin

# 4. 串口 115200 查看测试输出
```
