# CCO / ECU 编译打包（make cco / make ecu）

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
| `VER_YEAR/MONTH/DAY` | 同上 | 版本日期（BCD），如 `0x26/0x04/0x22` → 26/04/22 |
| `DI_QU_MODE` | `app/diqu_conf.h` | 地区模式：`HU_NAN_MODE`/`AN_HUI_MODE`/`ZHE_JIANG_MODE`... |
| `FC_VERSION_L` | 同上（全局） | 小版本低 16 位；`isv = FC_SVERSION = (DI_QU_MODE<<16)|FC_VERSION_L` |
| `FC_VER_YEAR/MONTH/DAY` | 同上（全局） | 内部版本日期 `idate` |
| `BATCH_NUM` | 同上（按地区） | 批次号（如 "2601"） |
| `DI_QU_UTF8` | 同上（按地区） | 地区中文 UTF-8（zip 名前缀） |

版本字节嵌入 `misc/src/iap.c` 的 `prog_version[]`（`"fcversion:"` 后依次 SVERSION/HVERSION/VER日期/波特率/校验/厂商/芯片/isv/idate/地区/批次）；`make/scripts/bin2all.sh` 读取后自动命名所有输出。

## 标准流程（以"正式版 + 测试版 2 个程序"为例）

> **优先使用项目根一键脚本 `./build_fw.sh`**（若存在）。脚本自动完成 备份→改版本宏→make clean→编译（默认串行，--jobs N 可选并行且失败自动回退）→同步等待→字节校验→归档→恢复头文件。

1. 与用户确认版本字段映射（SVERSION/版本日期/isv/idate/批次/地区；**忽略误导字段**）。
2. 脚本方式（推荐）：
   ```bash
   ./build_fw.sh build ecu AN_HUI_MODE 002601 260910 260910 --label 正式版 --out 交付_ecu_安徽_正式版测试版
   ./build_fw.sh build ecu AN_HUI_MODE 002602 260616 260910 --label 测试版 --out 交付_ecu_安徽_正式版测试版
   ./build_fw.sh finalize 交付_ecu_安徽_正式版测试版 --readme 正式版/测试版
   ./build_fw.sh verify 交付_ecu_安徽_正式版测试版/正式版 --expect sv=002601 isv=090027 idate=260910
   ```
   - 每次 `build` 独立完成"备份→改宏→clean→编译→等待→校验→归档→恢复"，变体间互不影响；
   - 归档含 zip（`make clean` 不删 zip），`finalize` 从 zip 还原散文件 + 生成顶层 readme + 打总 zip 并校验；
   - 字节校验读固件 fcversion/iap 头，非文件名比对，防"改了宏但没生效"。
3. 手动方式（脚本不可用时的后备）：备份头文件；改 `DI_QU_MODE` + `SVERSION` + `VER_Y/M/D`（及 `FC_*` 如需）。
4. `make clean && make ecu jump`（全新构建必须串行，勿加 -j8；实测并行有 built-in.o 竞态会损坏产物）。
5. 立即归档 `firmware/*` → 交付目录（只拷 .zip 防后续 clean 误删）。
6. 恢复头文件；改下一变体版本号再编译（重复 3-5）。
7. 交付：`交付_xxx/{正式版,测试版}/` 各含 zip + flash/iap/upgrade + readme 版本对照，再打总 zip。

## 实测踩坑

- `map.sh` 无 x 位 / `-j8` 干净构建竞态（实测会符号错乱损坏产物，**必须串行**）/ `make clean` 误删归档 / /tmp 被清空：见入口「通用红线」。
- `fcode.txt` 若存在于项目根会被 bin2all.sh 读取 → 编译前检查清理。
- 输出命名对照：zip 名用地区中文（`安徽-2601-ECU-sv...zip`），bin 名用地区宏去 `_MODE`（`AN_HUI_hv0301_sv...`）。
- 版本串歧义案例：`sv2601-svdate260422-1401` 中 `1401` 可能为无关项，务必先确认。
- `make clean` 会递归删除 `*.bin/*.dat`（含归档目录内的），但**不删 .zip**。
- `build_fw.sh` 内部实测：全新串行 ~32~76s；`make -jN start_recursive_build` 并行递归在全新构建下会触发 `built-in.o` 链接竞态（`bsp_gpio.o` 符号错乱），已内置自动回退串行。
- 版本日期 `idate` 若要取"编译当天"，`FC_VER_*` 需显式改（如 260910 → `0x26/0x09/0x10`），脚本 `build` 第 5 参传 6 位 YYMMDD 即可。
