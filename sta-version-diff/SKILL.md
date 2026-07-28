---
name: sta-version-diff
description: STA firmware version release diff analysis. Generates two documents between any two git commits: a modification points doc (for developers/reviewers) and a testing concerns doc (for QA). Supports region-specific filtering by DI_QU_MODE macro.
---

# STA Version Diff Analysis Skill

## Usage

Provide two git commit hashes (old and new). The skill automatically analyzes the diff and generates two documents.

Basic workflow:
1. Get `git log --oneline --no-merges <old>..<new>` for commit list
2. Analyze `git diff --stat <old>..<new>` for file change overview  
3. Extract region-specific `#if` macro changes (e.g. `HU_NAN_MODE`)
4. Output two documents:
   - **Modification Points Doc** — for developers/reviewers
   - **Testing Concerns Doc** — for QA

---

## Output Templates

### Template 1: Modification Points Doc

```
# <Project> Firmware Version Modification Points (v<old> → v<new>)

> **Focusing on <REGION_MACRO> (DI_QU_MODE == <value>) changes only**
> **Range**: <old commit desc> → <new commit desc>
> **Timespan**: <date range>

---

## I. Version Info

| Item | Old | New | Changed |
|------|-----|-----|---------|
| SVERSION | xx | xx | Y/N |
| FC_VERSION_L | xx | xx | Y/N |
| BATCH_NUM | xx | xx | Y/N |
| Version Date | xx | **xx** | Y/N |

## II. Architectural Changes (affecting target region)

### 2.x <Change Title>

**Files**: <file paths>

**Change Description**:
- Old logic → New logic
- Impact on target region

**<Region> Impact**: Unchanged / Specific changes.

## III. Feature Module Changes (region-specific)

### 3.x <Module Name>

**Files**: <file paths>

**Changes**:
- List specific function/macro/logic changes
- Code snippets (#if guard changes, new function prototypes)

**<Region> Impact**: Detailed impact description.

## IV. Risk Checklist

| # | Risk | Description |
|---|------|-------------|
| 1 | xx | xx |

```

### Template 2: Testing Concerns Doc

```
# <Project> Firmware Testing Concerns (Only <Region> mode)

> **Only for DI_QU_MODE == <REGION_MACRO> (<value>)**
> **Range**: <old version> → <new version>
> **Other regions not in scope**

---

## 📋 Version Info Check

| Item | Old | New | Needs Test |
|------|-----|-----|------------|
| SVERSION | xx | xx | Y/N |
| Version Date | xx | **xx** | ✅ |

## 🚨 P0 — Must Test

### Test 1: <Feature Name>

**Reason**: <why>

**Test Method**:
| Sub-item | Operation | Expected |
|----------|-----------|----------|
| ① xx | xx | ✅ xx |

## 🟡 P1 — Recommended

### Test N: <Feature Name>

**Note**: <unchanged or minor impact>

**Test Method**: <brief>

## 🟢 P2 — Confirm Only

### Test M: <Feature Name>

<simple confirmation>

## ⚠ Risks

1. xx

## 📊 Smoke Test Checklist

| # | Test | Priority | Time |
|---|------|----------|------|
| 1 | xx | P0 | 10min |

```

---

## Region Macro Reference Table

| Region | Macro | Value |
|--------|-------|-------|
| 北京 | `BEI_JING_MODE` | `0x01` |
| 湖北 | `HU_BEI_MODE` | `0x02` |
| 河南 | `HE_NAN_MODE` | `0x03` |
| 河北 | `HE_BEI_MODE` | `0x04` |
| 山东 | `SHAN_DONG_MODE` | `0x05` |
| 江苏 | `JIANG_SU_MODE` | `0x06` |
| 辽宁 | `LIAO_NING_MODE` | `0x07` |
| 黑龙江 | `HEI_LONG_JIANG_MODE` | `0x21` |
| 宁夏 | `NING_XIA_MODE` | `0x08` |
| 内蒙 | `NEI_MENG_MODE` | `0x09` |
| 新疆 | `XIN_JIANG_MODE` | `0x0A` |
| 重庆 | `CHONG_QING_MODE` | `0x0B` |
| 甘肃 | `GAN_SU_MODE` | `0x17` |
| 上海 | `SHANG_HAI_MODE` | `0x18` |
| 湖南 | `HU_NAN_MODE` | `0x19` |
| 四川 | `SI_CHUAN_MODE` | `0x0F` |
| 四川水电 | `SI_CHUAN_SHUI_DIAN_MODE` | `0x20` |
| 陕西 | `SHAAXNI_MODE` | `0x10` |
| 山西 | `SHAN_XI_MODE` | `0x11` |
| 天津 | `TIAN_JIN_MODE` | `0x12` |
| 浙江 | `ZHE_JIANG_MODE` | `0x13` |
| 福建 | `FU_JIAN_MODE` | `0x14` |
| 安徽 | `AN_HUI_MODE` | `0x15` |
| 青海 | `QING_HAI_MODE` | `0x16` |
| 通用 | `COMMON_MODE` | `0xFF` |

---

## Git Commands Reference

```bash
# List commits between two versions
git log --oneline --no-merges <old>..<new>

# File change statistics
git diff --stat <old>..<new>

# List added files
git diff --diff-filter=A --name-status <old>..<new>

# List deleted files
git diff --diff-filter=D --name-status <old>..<new>

# Search for specific macro changes
git diff <old>..<new> -- . | grep -n "HU_NAN\|DI_QU_MODE"

# View detailed changes in specific file
git diff <old>..<new> -- <filepath>

# View old version file content
git show <old>:<filepath>
```

---

## Analysis Notes

1. **Macro Isolation**: `diqu_conf.h` defines `DI_QU_MODE` for the target region. Always check this file first.
2. **Version Parameters**: Check `diqu_conf.h` (`FC_VERSION_L`, `BATCH_NUM`, `INTERNAL_VER_DATE`) and `yxsm_conf.h` (`SVERSION`, `VERSION_DATE`) for version changes.
3. **Architectural Changes**: Non-macro-guarded generic changes (e.g. `_meter_prase()` refactoring) affect all regions — must be explicitly noted.
4. **New Regions**: If new region macros appear (e.g. `HEI_LONG_JIANG_MODE`, `SI_CHUAN_SHUI_DIAN_MODE`), these are new region additions and do not affect the target region.
5. **Freeze Changes**: Freeze-related changes (`sector_manager.c`, `fj_data_freeze.c`, `sta_extend_cmd.c`) typically affect Shanxi/Hunan/Shaanxi/Fujian regions.
6. **DLL Auth**: Hunan-specific auth functions (`table70_auth`, `table76_auth`) are in `management_message.c`, guarded by `#if DI_QU_MODE == HU_NAN_MODE`.
