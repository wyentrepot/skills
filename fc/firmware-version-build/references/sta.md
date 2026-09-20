# STA 编译打包（sta_venus2m* 变体）

原 `sta-version-build` 主体迁移至此层。

## 仓库与构建

- 仓库：`/home/H_STA/04/sta`；`make` 必须在 `sta/` 目录下运行（Makefile 相对路径基于 sta/）。
- 版本宏：`sta/protocol/aps/yxsm_conf.h`（`SVERSION`、`VERSION_DATE_Y/M/D`）、`sta/protocol/aps/diqu_conf.h`（`DI_QU_MODE`、`FC_VERSION_L`、`INTERNAL_VER_DATE_Y/M/D`、`BATCH_NUM`）。
- 命名：`{地区}-{批次}-STA-sv{mSVer}-{date}-isv{FC_SVERSION}-idate{INTERNAL_VER_DATE}-1.zip`（`make/scripts/bin2dat.sh`）。
- 输出：`sta/firmware/{TARGET}/`；归档：`archive_{TARGET}/`（项目根）。

## 本层唯一执行路径（脚本）

**STA 固件版本编译一律用技能脚本 `scripts/build_variants.sh`**，单/多编译由输入参数决定，勿手搓。脚本唯一权威源在技能目录，**无需复制进仓库**，任何位置可运行：

```bash
SK=/home/02-skill-fc/skills/fc/firmware-version-build/scripts/build_variants.sh
$SK --dry-run --repo /home/H_STA/02/sta    # 先干跑: 打印基线+变体版本矩阵与预期 zip 名，确认后
$SK --repo /home/H_STA/02/sta              # 多编译(默认): 大同小异 + 小同大异 两变体
$SK --repo /home/H_STA/02/sta --variants datong_xiaoyi   # 单编译: 只出一个变体
# 也可不传 --repo：进入仓库内任意子目录后运行（自动向上探测）；
# 或用环境变量: STA_REPO=/home/H_STA/02/sta $SK
```

- **路径保护**：仓库定位优先级 `--repo` > `$STA_REPO` > 当前目录向上自动探测；未定位到合法 STA 仓库（缺版本头文件/Makefile/目标）一律拒绝执行；执行前打印"操作仓库"。
- 单/多编译 = 脚本参数：`--variants "datong_xiaoyi xiaotong_dayi"`（默认两变体）或 `--variants datong_xiaoyi`（单变体）。
- 默认 `TARGET=sta_venus2m_v7`；可 `$SK sta_venus2m`、`--variants "..."`、`--force`（头文件有未提交改动时）。
- 产物：`archive_{TARGET}/{变体}/`（全量）+ `{TARGET}_firmware.zip`（各变体仅 zip + 版本对照 readme），落在**定位到的仓库根目录**。
- 脚本内置：基线读取（块作用域定位宏，跨地区安全）、预期 zip 名校验（sv/date/isv/idate 字段）、每变体编译后立即归档并恢复头文件、任一步失败 trap 自动恢复。
- 脚本前置要求：目标仓库为 git 仓库、版本头文件无未提交改动、`make clean` 后**串行** `make {TARGET} jump`（见红线 8）。
- 脚本对 agent 的价值：一次后台调用替代 ~15 次工具往返；仅"确认基线 + 校验交付物"需要 agent 介入。

> 以下手动流程仅作脚本异常时的排查参照，不当作并行流程。

## 前置：确定编译目标 (TARGET)

| 目标类型 | make target |
|---|---|
| STA v2 / v7 | `sta_venus2m` / `sta_venus2m_v7`（v7 默认常用） |
| II采 | `clt2_venus2m` / `clt2_venus2m_v7` |
| 中继器 | `rpter_venus2m` / `rpter_venus2m_v7` |
| 组合构建 | `sta` / `clt2` / `rpter` / `venus2m` / `venus2m_v7` |

> 目标以当前 `/home/H_STA/04/sta/Makefile` 为准（实测当前分支无 `sta_venus2m_v7_hrf`、`sta_venus2m_shanxi_liang_ce`；历史/其他分支可能出现过，用前先 `grep -o` 确认）。

选定 TARGET 后，输出目录 `sta/firmware/{TARGET}/`、归档目录 `archive_{TARGET}/`、make 命令、cp 源路径、最终 zip 名全部以 `{TARGET}` 同步替换。

## 操作前准备

1. 读当前基线值（不同地区值不同）：

   ```bash
   grep -n 'SVERSION\|VERSION_DATE_[YMD]\|FC_VERSION_L\|INTERNAL_VER_DATE_[YMD]\|BATCH_NUM\|DI_QU_MODE' \
     sta/protocol/aps/yxsm_conf.h sta/protocol/aps/diqu_conf.h
   ```

2. 确定今日日期（无前导零），如 `26/7/14`。

## 三组变体（大小版本差异）

| 角色 | 宏 | 基线 | 大同小异 | 小同大异 |
|---|---|---|---|---|
| 大版本 | `SVERSION` | `0x00XXXX` | 同基线 | +1 |
| 大版本日期 | `VERSION_DATE_Y/M/D` | `Y/M/D` | 同基线 | 今日 |
| 小版本 | `FC_VERSION_L` | `0xXXX` | +1 | 同基线 |
| 小版本日期 | `INTERNAL_VER_DATE_Y/M/D` | `Y/M/D` | 今日 | 同基线 |

## 执行步骤（每变体）

1. 备份：`cp sta/protocol/aps/diqu_conf.h sta/protocol/aps/yxsm_conf.h /tmp/sta-orig-bak/`。
2. 改对应宏（大同小异：小版本 +1、小版本日期=今日；小同大异：大版本 +1、大版本日期=今日）。
3. 编译（在 sta/ 下）：

   ```bash
   cd sta && make clean && make {TARGET} jump -j8 && cd ..
   ```

   若全新构建报 `No rule to make target 'built-in.o'`（all 目标的递归构建与链接并行竞态），改用**串行** `make {TARGET} jump`。
4. **立即归档**（输出目录在每次链接前被清空，make 一完成就拷贝）：

   ```bash
   mkdir -p archive_{TARGET}/<变体>        # 变体: baseline | datong_xiaoyi | xiaotong_dayi
   cp sta/firmware/{TARGET}/*.bin sta/firmware/{TARGET}/*.dat \
      sta/firmware/{TARGET}/*.zip sta/firmware/{TARGET}/readme.txt archive_{TARGET}/<变体>/
   cp -r sta/firmware/{TARGET}/debug archive_{TARGET}/<变体>/debug
   ```

5. 恢复头文件：`cp /tmp/sta-orig-bak/{diqu_conf,yxsm_conf}.h sta/protocol/aps/`。

## 最终打包（交付物）

```bash
# 子目录只留 zip（删 .bin/.dat/debug），根加 readme（版本对照 + 区名映射）
for dir in baseline datong_xiaoyi xiaotong_dayi; do
  rm -f archive_{TARGET}/$dir/*.bin archive_{TARGET}/$dir/*.dat \
        archive_{TARGET}/$dir/readme.txt
  rm -rf archive_{TARGET}/$dir/debug
done
rm -f {TARGET}_firmware.zip
cd archive_{TARGET} && zip -r ../{TARGET}_firmware.zip . && cd ..
```

## 关键避坑

1. `make` 必须在 `sta/` 下；`make clean` 删的是 `sta/firmware/*`（不是项目根 firmware/）。
2. 固件输出在 `sta/firmware/{TARGET}/`；归档 `cp` 源路径必须是它。
3. 输出目录每次链接前被清空 → 每次 make 完成后立即拷贝归档。
4. 变体间必须 `make clean`，否则 .o 用旧宏值。
5. 日期值不能带前导零（八进制陷阱）：用 `7` 而非 `07`。
6. `jump` 必须作第二参数：`make {TARGET} jump [-j8]`，否则 bin2dat.sh 在 stdin 等待。
7. zip 中文名在非中文终端显示乱码 → 最终交付用 ASCII 缩写重命名或写 readme 映射。
8. `FC_SVERSION` = `(DI_QU_MODE<<16) | (PLATFORM<<12) | (FC_VERSION_L&0xfff)`；`PLATFORM` 在 VENUS_V7=1、VENUS_V2=0。
