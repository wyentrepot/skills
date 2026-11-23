# 双代 SDK 兼容编译（dual-gen-build）

> 来源：0005（预研交付）+ 0006（重演加固）。目标形态：`make cco_v3`（新代）/ `make cco`（旧代）/ `make ecu`（旧代+ECU 宏），互不手工 clean。

## 四件套（缺一即翻车）

### 1. 影子树
- 旧 SDK 整树搬到 `bsp/venus_sdk_v2/`（92 文件全量 + **hwl.h 镜像件**）。
- hwl.h 镜像件是关键机关：相对包含按"包含者目录"解析，镜像件放哪代就点亮哪代；-I 插序解不了。
- 落位后逐文件 md5 对照 feature 原版；清掉 checkout 混入的构建残留与新代文件。
- 旧代还要编影子树自己的 libdepend（防 ABI 错配，见 0006 步骤 6）。

### 2. SDK_VER 单维参数化（Makefile）
```make
ifeq ($(SDK_VER_LEGACY),)
PRJ_SDK_DIR := $(TOPDIR)/bsp/venus/sdk          # 新代
else
PRJ_SDK_DIR := $(TOPDIR)/bsp/venus_sdk_v2/sdk   # 旧代影子树
endif
```
- 一个变量管全部代次取值：路径 / 宏组（VENUS_V2 等）/ lds（venus8m_v2/psram_10m）/ 镜像标识（0xFC011031 旧 / 0x22030117 新）/ -v 基址。
- 判旧用 `$(filter ver_03-00-02-08 ...,$(SDK_VER))`；加版本只加取值。
- 缺省=新代且**取值逐字节不动**（新代零扰动硬门）。
- 旧代分支还要切：asic 寄存器头 -I（venus_v2）、hwl.h 开关 -I 插前。

### 3. 文件级代次选择（BSP 层）
```make
ifneq ($(filter ver_03-00-02-08,$(SDK_VER)),)
obj-y += bsp_ticktimer_v2.o   # 旧版逐字节恢复
else
obj-y += bsp_ticktimer.o      # 新代适配版，一字不动
endif
```
- **为什么不用行内 #if**：logger.h 把 `__LINE__` 编进二进制，行内条件会让新代指纹漂移，破坏字节门。
- 改过的文件命名 `*_v2.c`（旧版）+ 原文件（新版），Makefile 按代选。
- flash.h 这类"宏按代分叉"特例：直译宏（旧代，feature 原样）vs 函数版（新代）两个分支各定义各的。

### 4. 打包链按代选 boot
- bin2all.sh 接 SDK_VER 第三参（Makefile `all` 内嵌调用要传够，原两参致 SDK_VER 落 jump_set 位恒走新代门——0006 实测）。
- md5 硬门两代各自生效：新 boot `078d4830` / 旧 boot `88083d48`（002 工程口径）。
- 镜像标识互挡是第二重防线：旧镜像 0xFC… / 新镜像 0x22…，跨代升级会被 boot 拒绝。

## 切代自洁（跨代污染防线）

```make
.sdk_ver_stamp:
	@echo $(SDK_VER) > $@; $(CLEAN_GENERATED)
```
- 两代共用 .o 路径 + .d 只记编译当时头路径 → 切代不 clean 会复用上代目标文件，静默出错代固件
  （实测症状：链接报 get_decrypt_key / bsp_wd undefined）。
- **无戳记（首次）也要清**——"无戳记不清理"是实测盲区。
- 验收：v3→cco→v3→cco 不手工 clean，双向产物各回基线；切换提示出现 2 次符合预期。

## 目标命名与宏绑定（0006 变更 2 口径，H_CCO/002 现行）

| 目标 | 代次 | 板宏 | iap 头标识 |
|---|---|---|---|
| make cco_v3 | 新代 ver_03-00-03-11 | CCO_BOARD_V303 | 0x22030117 |
| make cco | 旧代 ver_03-00-02-08 | （无） | 0xFC011031 |
| make ecu | 旧代 | ECU2_BOARD | 0xFC011031 |

> 命名与代次的绑定属需求口径，动工前经用户拍板写进 REQS，不擅自改名。

## 存储区地址按代分叉

- 黑名单存储区：旧代 0x37000 / 新代 0x4b000，兼容块按代自动切换（BLK_STORE_ADDR×6）。
- BOARD_CFG 写地址两处（iap_flash.c IAP 切槽 / phy_sal.c RF 校准落盘）必须用 `BOARD_CFG_ADDR`
  而非 `(uint32_t)BOARD_CFG`（后者新代=函数返回 SRAM 指针，过不了 flash_write 地址校验，静默失败）。
