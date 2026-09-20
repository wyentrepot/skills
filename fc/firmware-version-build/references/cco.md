# CCO / ECU 编译打包（make cco / make ecu）

## 本层唯一执行路径（脚本）

**CCO/ECU 固件版本编译一律用技能脚本 `scripts/build_cco.sh`**，单/多编译由输入参数决定，勿手搓：

```bash
SK=/home/02-skill-fc/skills/fc/firmware-version-build/scripts/build_cco.sh

# 单编译: 一次 build 调用
$SK --repo /home/H_CCO/001/cco build cco ZHE_JIANG_MODE 002601 260903 260916
$SK --repo /home/H_CCO/001/cco build ecu AN_HUI_MODE 002601 260910 260910

# 多编译(正式版+测试版): 多次 build 调用, 每次独立 备份→改宏→clean→编译→校验→归档→恢复
$SK --repo /home/H_CCO/001/cco build ecu AN_HUI_MODE 002601 260910 260910
$SK --repo /home/H_CCO/001/cco build ecu AN_HUI_MODE 002602 260616 260910

# 先干跑确认(只打印将改的宏与预期 zip 名)
$SK --repo /home/H_CCO/001/cco --dry-run build cco ZHE_JIANG_MODE 002601 260903 260916
```

参数：`build <cco|ecu> <DI_QU_MODE> <SVERSION6> <VDATE6> <IDATE6>`；
小版本 `FC_VERSION_L` / 批次 / 地区UTF8 随 `DI_QU_MODE` 分支块生效，无需传参。

- 仓库定位：`--repo` > `$CCO_REPO` 环境变量 > 当前目录向上自动探测；未定位到合法 CCO 仓库一律拒绝执行（路径保护）。
- 产物：`<仓库>/archive_<target>/sv<SVER>_d<VDATE>_id<IDATE>/`（zip + flash + iap + upgrade + readme），可用 `--out <dir>` 改目录。
- 脚本内置：块作用域改宏（跨地区安全）、预期 zip 名校验（sv/date/isv/idate 字段）、编译后立即归档并恢复头文件、失败 trap 自动恢复。
- 动工前仍须与用户确认版本字段映射（红线 1）；以下手动流程仅作脚本异常时的排查参照。

## 仓库与构建

- 仓库：`/home/H_CCO/001/cco`；`make` 必须在项目根运行（`TOPDIR=$(shell pwd)`）。
- 目标：`make cco`（CCO 模块）、`make ecu`（ECU 模块，等价 `TARGET=ecu` + `-DECU2_BOARD`，芯片同为 venus8m）。
- 输出：`firmware/` 下自动生成 `flash_{cco|ecu}_*.bin`、`iap_{cco|ecu}_*.bin`、`upgrade_{cco|ecu}_*.dat`、`readme.txt`、`{地区}-{批次}-{CCO|ECU}-sv...-1.zip`。
- **输出用途（烧录文件选择铁律，2026-09-10 实测教训）**：
  - `flash_*.bin` = **生产烧录文件**（整片 flash 镜像，~2MB），产线烧录器用；**不是串口升级文件**。
  - `iap_*.bin` = **IAP 串口升级文件**（~几百 KB），bootloader XMODEM 串口升级用 → **升级/测试烧录用它**。
  - `upgrade_*.dat` = 另一条 `upgrade` 串口升级格式。
  - 用 `flash_*.bin` 走 bootloader 升级会在 ~24%（约 503KB，iap 镜像范围外）后模块中止（"timeout"→"cancel"→退回 shell）；不确定先读 `firmware/readme.txt`。

## 版本宏（头文件）

| 宏 | 文件 | 说明 |
|---|---|---|
| `SVERSION` | `app/yxsm_conf.h`（按 `DI_QU_MODE` 分区） | 大版本号，如 `0x002601` |
| `VER_YEAR/MONTH/DAY` | 同上 | 版本日期（BCD），如 `0x26/0x09/0x03` → 260903 |
| `DI_QU_MODE` | `app/diqu_conf.h` | 地区模式：`HU_NAN_MODE`/`AN_HUI_MODE`/`ZHE_JIANG_MODE`... |
| `FC_VERSION_L` | 同上（全局） | 小版本低 16 位；`isv = FC_SVERSION = (DI_QU_MODE<<16)|FC_VERSION_L` |
| `FC_VER_YEAR/MONTH/DAY` | 同上（全局） | 内部版本日期 `idate`（BCD） |
| `BATCH_NUM` | 同上（按地区） | 批次号（如 "2601"） |
| `DI_QU_UTF8` | 同上（按地区） | 地区中文 UTF-8（zip 名前缀） |

版本字节嵌入 `misc/src/iap.c` 的 `prog_version[]`（`"fcversion:"` 后依次 SVERSION/HVERSION/VER日期/波特率/校验/厂商/芯片/isv/idate/地区/批次）；`make/scripts/bin2all.sh` 读取后自动命名所有输出。zip 名为 `{地区}-{批次}-{CCO|ECU}-sv{mSVer}-{date}-isv{isv}-idate{idate}-1.zip`。

## 实测踩坑

- `map.sh` 无 x 位 / `-j8` 干净构建竞态（实测会符号错乱损坏产物，**必须串行**）/ `make clean` 误删归档 / /tmp 被清空：见入口「通用红线」。
- `fcode.txt` 若存在于项目根会被 bin2all.sh 读取 → 编译前检查清理。
- 输出命名对照：zip 名用地区中文（`安徽-2601-ECU-sv...zip`），bin 名用地区宏去 `_MODE`（`AN_HUI_hv0301_sv...`）。
- 版本串歧义案例：`sv2601-svdate260422-1401` 中 `1401` 可能为无关项，务必先确认。
- `make clean` 会递归删除 `*.bin/*.dat`（含归档目录内的），但**不删 .zip**。
- 全新串行 ~32~76s；`make -jN` 并行递归在全新构建下会触发 `built-in.o` 链接竞态（`bsp_gpio.o` 符号错乱），必须串行（脚本默认）。
- 版本日期 `idate` 取"编译当天"：脚本 `IDATE6` 传当日 `YYMMDD` 即可（内部自动转 BCD `0xYY/0xMM/0xDD`）。
