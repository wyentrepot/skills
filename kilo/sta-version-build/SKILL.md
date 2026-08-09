---
name: sta-version-build
description: STA 固件大小版本自动编译打包技能。针对任意 DI_QU_MODE 执行基线、大同小异、小同大异三组变体编译，自动生成 zip 并归档。支持多次执行（自动清理上次产物）。
---

# STA 固件版本编译打包

## 适用场景

对 `sta/` 主树中任意地区配置（由 `diqu_conf.h` 中 `DI_QU_MODE` 决定），通过修改 `SVERSION` / `VERSION_DATE`（大版本）和 `FC_VERSION_L` / `INTERNAL_VER_DATE`（小版本）生成三组不同固件变体并归档。

## 相关文件

| 文件 | 作用 |
|---|---|
| `sta/protocol/aps/yxsm_conf.h` | `SVERSION` — 大版本号；`VERSION_DATE_Y/M/D` — 大版本日期 |
| `sta/protocol/aps/diqu_conf.h` | `DI_QU_MODE` — 地区模式；`FC_VERSION_L` — 小版本号；`INTERNAL_VER_DATE_Y/M/D` — 小版本日期；`BATCH_NUM` — 批次号 |
| `sta/Makefile` | 构建入口（`make` 必须在 `sta/` 目录下运行） |
| `sta/make/scripts/bin2dat.sh` | 从编译后的二进制提取版本信息，自动生成所有输出文件名并打包 zip |

## 操作前准备

1. 读取当前基线值（不同地区值不同）：

   ```bash
   grep -n 'SVERSION\|VERSION_DATE_[YMD]\|FC_VERSION_L\|INTERNAL_VER_DATE_[YMD]\|BATCH_NUM\|DI_QU_MODE' \
     sta/protocol/aps/yxsm_conf.h sta/protocol/aps/diqu_conf.h
   ```

2. 确定今日日期（无前导零），例如 `26/7/14`。

3. 根据基线值填入版本映射表（示例模板）：

   | 角色 | 宏 | 基线 | 大同小异 | 小同大异 |
   |---|---|---|---|---|
   | 大版本 | `SVERSION` | `0x00XXXX` | 同基线 | `0x00XXXX` +1 |
   | 大版本日期 | `VERSION_DATE_Y/M/D` | `Y/M/D` | 同基线 | 今日日期 |
   | 小版本 | `FC_VERSION_L` | `0xXXX` | +1 | 同基线 |
   | 小版本日期 | `INTERNAL_VER_DATE_Y/M/D` | `Y/M/D` | 今日日期 | 同基线 |

## 执行步骤

**重要：`make` 必须在 `sta/` 目录下运行，但归档命令在项目根目录下操作。多次执行时，必须先清理上一次产物。**

### 清理上一次产物（如果是重复执行）

```bash
# 删除上一次的归档目录和最终 zip，避免新旧文件混合
rm -rf archive_sta_venus2m_v7
rm -f *_firmware_v7_*.zip

# 删除构建输出（但 make clean 也会做）
rm -rf sta/firmware
```

### 前置准备

```bash
# 在项目根目录执行
mkdir -p /tmp/sta-orig-bak
cp sta/protocol/aps/diqu_conf.h sta/protocol/aps/yxsm_conf.h /tmp/sta-orig-bak/
```

### 编译基线

```bash
# 在 sta/ 目录下编译
cd sta && make clean && make sta_venus2m_v7 jump -j8 && cd ..
```

归档输出（`make` 的输出在 `sta/firmware/` 下）：

```bash
mkdir -p archive_sta_venus2m_v7/baseline
cp sta/firmware/sta_venus2m_v7/*.bin sta/firmware/sta_venus2m_v7/*.dat \
   sta/firmware/sta_venus2m_v7/*.zip sta/firmware/sta_venus2m_v7/readme.txt \
   archive_sta_venus2m_v7/baseline/
cp -r sta/firmware/sta_venus2m_v7/debug archive_sta_venus2m_v7/baseline/debug
```

### 大同小异（改小版本）

```bash
# 1. 修改 diqu_conf.h（值不带前导零，否则会被编译器视为八进制常量）
#    编辑 sta/protocol/aps/diqu_conf.h：
#    FC_VERSION_L 0xXXX → 0xXXX+1
#    INTERNAL_VER_DATE_Y/M/D → 今日日期

# 2. 编译（在 sta/ 目录下）
cd sta && make clean && make sta_venus2m_v7 jump -j8 && cd ..

# 3. 归档
mkdir -p archive_sta_venus2m_v7/datong_xiaoyi
cp sta/firmware/sta_venus2m_v7/*.bin sta/firmware/sta_venus2m_v7/*.dat \
   sta/firmware/sta_venus2m_v7/*.zip sta/firmware/sta_venus2m_v7/readme.txt \
   archive_sta_venus2m_v7/datong_xiaoyi/
cp -r sta/firmware/sta_venus2m_v7/debug archive_sta_venus2m_v7/datong_xiaoyi/debug

# 4. 恢复 diqu_conf.h
cp /tmp/sta-orig-bak/diqu_conf.h sta/protocol/aps/diqu_conf.h
```

### 小同大异（改大版本）

```bash
# 1. 修改 yxsm_conf.h（值不带前导零）
#    编辑 sta/protocol/aps/yxsm_conf.h：
#    SVERSION 0x00XXXX → 0x00XXXX+1
#    VERSION_DATE_Y/M/D → 今日日期

# 2. 编译（在 sta/ 目录下）
cd sta && make clean && make sta_venus2m_v7 jump -j8 && cd ..

# 3. 归档
mkdir -p archive_sta_venus2m_v7/xiaotong_dayi
cp sta/firmware/sta_venus2m_v7/*.bin sta/firmware/sta_venus2m_v7/*.dat \
   sta/firmware/sta_venus2m_v7/*.zip sta/firmware/sta_venus2m_v7/readme.txt \
   archive_sta_venus2m_v7/xiaotong_dayi/
cp -r sta/firmware/sta_venus2m_v7/debug archive_sta_venus2m_v7/xiaotong_dayi/debug

# 4. 恢复 yxsm_conf.h
cp /tmp/sta-orig-bak/yxsm_conf.h sta/protocol/aps/yxsm_conf.h
```

### 最终打包（交付物）

清理子目录只保留 zip（不要 .bin/.dat/debug），添加 readme，打包成一个 zip。

**注意：`bin2dat.sh` 生成的中文名 zip（如 `湖南-...zip`）在部分终端会显示乱码，最终打包时用 ASCII 名重命名。**

```bash
# 清理子目录，只保留 zip 文件
for dir in baseline datong_xiaoyi xiaotong_dayi; do
  rm -f archive_sta_venus2m_v7/$dir/*.bin \
        archive_sta_venus2m_v7/$dir/*.dat \
        archive_sta_venus2m_v7/$dir/readme.txt
  rm -rf archive_sta_venus2m_v7/$dir/debug
done

# 创建根目录 readme.txt（包含版本对照说明）
cat > archive_sta_venus2m_v7/readme.txt << 'EOF'
填写版本对照说明...
区名映射: XX=地区 (例如 HN=湖南, AH=安徽, HB=湖北)
文件名: {区名}-{批次}-STA-sv{SVERSION}-{日期}-isv{FC_SVERSION}-idate{INTERNAL_VER_DATE}-1.zip
EOF

# 打成最终 zip（用 ASCII 文件名避免中文编码问题）
rm -f XXXX_STA_firmware_v7_XXXX.zip
cd archive_sta_venus2m_v7 && zip -r ../XXXX_STA_firmware_v7_XXXX.zip . && cd ..
```

### 最终结构

```
archive_sta_venus2m_v7/
├── readme.txt
├── baseline/
│   └── {地区}-{批次}-STA-sv{SVERSION}-{VERSION_DATE}-isv{FC_SVERSION}-idate{INTERNAL_VER_DATE}-1.zip
├── datong_xiaoyi/
│   └── ...isv{FC_SVERSION+1}-idate{今日}...
└── xiaotong_dayi/
    └── ...sv{SVERSION+1}-{今日}...
```

## 关键避坑

1. **`make` 必须在 `sta/` 目录下运行** — Makefile 中所有相对路径基于 `sta/`。`make clean` 会删除 `sta/firmware/*`，不是项目根目录的 `firmware/`。

2. **固件输出在 `sta/firmware/sta_venus2m_v7/`** — 不是 `firmware/sta_venus2m_v7/`。所有归档的 `cp` 源路径必须为 `sta/firmware/sta_venus2m_v7/...`。

3. **`make clean` 会执行 `$(RM) firmware/*`** — 清除所有子目录。归档必须放在 `firmware/` **之外**（如项目根目录的 `archive_sta_venus2m_v7/`）。

4. **`$(RM) $(PRJ_BIN_DIR)/*` 在每个 ELF 链接规则前执行** — 输出目录在每次构建开始时被清空。**每次 `make` 完成后立即拷贝输出文件到归档目录。**

5. **每次变体编译前必须 `make clean`** — 版本宏定义在 `.h` 头文件中，不 `make clean` 会导致 `.o` 文件使用旧值。

6. **日期值不能有前导零** — C 编译器把 `08ul` 视为无效八进制常量。使用 `8ul` 而非 `08ul`，`7ul` 而非 `07ul`。

7. **版本号格式**：
   - `FC_SVERSION` 由 `diqu_conf.h` 中宏计算：`(DI_QU_MODE<<16) | (PLATFORM<<12) | (FC_VERSION_L&0xfff)`
   - 例如湖南 `DI_QU_MODE=0x19`、`VENUS_V7(PLATFORM=1)` → `FC_SVERSION` 格式 `0x191xxx`
   - zip 命名规则（来自 `bin2dat.sh:330`）：`{地区UTF8}-{批次}-STA-sv{mSVer}-{date}-isv{内部版本}-idate{内部日期}-1.zip`

8. **`jump` 参数必须作为第二个参数传入** — 如 `make sta_venus2m_v7 jump -j8`，否则 `bin2dat.sh` 会在 stdin 等待用户输入。

9. **备份-修改-恢复模式** — 每步修改前确保有原始备份（`/tmp/sta-orig-bak/`），修改后编译归档，立即恢复原始值，确保步间互不影响。

10. **zip 文件名中文乱码** — `bin2dat.sh` 以地区中文名命名 zip（如 `湖南-...zip`），在非中文终端下会显示为乱码。最终交付的 zip 应用 ASCII 缩写（`HN`/`AH`/`HB` 等）重命名子 zip，或直接写 readme 说明映射关系。
