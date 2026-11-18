# 构建海思 GW 工程（build）

> 适用：海思 DW31 的 GW 固件工程（CMake + SDK 体系）。工程根 `PROJECT` 按 `SKILL.md` §1 解析
> （特征：含 `scripts/build.sh` 与 `build/config/DW31v100/`），**本文不写死路径**。
> **与 `firmware-version-build` 不是一套**：那个是 `make cco/sta_venus2m*` 的模块工程；
> 海思 GW 一律用本文件的 `scripts/build.sh`，不要混用 make 流程。
> 状态：用法与产物目录按 2026-11-17 现场核对；**端到端重编译尚未在完整会话里跑过**（下次补一次并回填耗时）。

## 0 前置（先读工程规则）

- `PROJECT` 上级若存在 `.agent/RULES.md`，它是强制的，先读。
- 只在 `PROJECT` **原工程**里改/编，禁止 worktree / 独立 git 树 / 工程副本。
- 工作区可能有未提交改动（`vendor_bridge.cmake.in`、`Platform/plc-sdk` 子模块、`Application/ecu_port/` 等）：
  未经用户授权**不得** `checkout/reset/clean/stash`；**禁止 `git push`**。
- 子模块指针要对：`git -C "$PROJECT" submodule status Platform/plc-sdk` 应与交付件 `COMMIT.txt` 一致。

## 1 一条命令定档（不要用环境变量开关）

```bash
cd "$PROJECT"
bash scripts/build.sh sg_fusion_cco   # 融合终端 / ECU 产品件 → out/sg_fusion_cco/
bash scripts/build.sh sg_cco          # 国网 CCO（不编译 ECU 组件）→ out/sg_cco/
bash scripts/build.sh sg_sta          # STA → out/sg_sta/
bash scripts/build.sh clean           # 清 SDK 输出
```

| 目标 | 是什么 | 产品类型 | 版本注入 |
|---|---|---|---|
| `sg_fusion_cco` | **融合终端（ECU）产品家族**；UART0 460800 8E1 业务 + UART3 管理通道 | 501 | 构建期注入 `ECU_VERSION`，默认 `DW31_V100R001C00SPC055` |
| `sg_cco` | 国网 CCO（不编 ECU 组件） | CCO | 保持 SDK 原值（SPC050） |
| `sg_sta` | STA | STA | 保持 SDK 原值 |

- 临时换版本串：`ECU_VERSION=DW31_V100R001C00SPC056 bash scripts/build.sh sg_fusion_cco`；
  注入在构建期完成、退出时自动还原 SDK 文件（版本差异不落进源文件）。
- 构建脚本会把 Fusion 开关、波特率宏、归档目录一次定好；**不要再手工改 `vendor_build_option.cmake`**。

## 2 产物在哪

```
$PROJECT/out/sg_fusion_cco/bin/
  DW31_mcore_sg_cco.bin                    原始镜像
  DW31v100_mcore_sg_cco_upg.bin            ★ 在线升级包（0x3412/0x3415/0x3419）
  signed_DW31v100_mcore_sg_cco.bin / .lzma 签名/压缩件
  DW31_mcore_sg_cco.{asm,elf,map,ld}       调试/符号
  nv_cco_*.bin / params_cco*.bin           NV 与参数分区
$PROJECT/out/sg_fusion_cco/image/
  DW31v100_mcore_sg_cco_image.fwpkg        ★ BurnTool 整包（7 分区，需断电/上电）
  DW31v100_mcore_sg_cco_upg.hupg           与 upg.bin 逐字节相同
```

**别按文件名认产品族**：CCO 与融合终端的在线包**都叫** `DW31v100_mcore_sg_cco_upg.bin`，
只有目录（`out/sg_cco/` vs `out/sg_fusion_cco/`）和构建目标不同。烧错族的直接后果是模块回
`0x8007 EXT_ERR_BAD_DATA`（见 `upgrade.md` §1.1）。

## 3 交给 8765 做在线升级时的路径白名单

- 白名单在服务端配置（见 `contract.md` §3.2）；当前接受 `C:\fc_diag_client` 与工程 `out/` 整棵。
- 工程 `out/` 在白名单里时，直接用 `out/sg_fusion_cco/bin/..._upg.bin` 即可；
  拷到 `发行件/` 等目录反而会被 400「路径不在白名单」拒掉 → 复制到 `C:\fc_diag_client\samples\` 再 prepare。
- **包族必须对**：融合终端/ECU 只烧 `out/sg_fusion_cco/`；CCO 只烧 `out/sg_cco/`。

## 4 自检与对账

```bash
ls -l "$PROJECT"/out/<target>/bin/DW31v100_mcore_sg_cco_upg.bin
md5sum "$PROJECT"/out/<target>/bin/DW31v100_mcore_sg_cco_upg.bin    # 与交付说明/COMMIT.txt 对账
git -C "$PROJECT" status --short | head    # 构建后工作区不该多出脏文件
git -C "$PROJECT" submodule status Platform/plc-sdk
```

- 2026-11-18 实测（合入 plc-sdk main 三项修复后，SPC055）：`sg_fusion_cco` 产物 `upg.bin`
  **458,336 B**、md5 `08517a58…`、sha256 `fabeaee0…`（`.hupg` 同字节）；`prepare` 实测取到
  `approval_id`，`package.size=458336`。**包长会随 SDK 改动变化，对账以当次构建的 md5/sha256 为准，
  不要拿旧哈希判"包不对"**。
- 2026-11-17 实测：同目标 `upg.bin` 458,000 B、md5 `db0ee959…`、sha256 `95c0350f…`；
  `发行件/20261117-SPC055-业务460800` 那个 CCO 族包是 457,952 B、md5 `92b26ead…`。

## 5 常见坑

| 现象 | 原因/处理 |
|---|---|
| 编译报 SDK 文件冲突 | 工作区有未提交改动或子模块指针不对；按工程规则备份→核对，**不要** clean 掉用户改动 |
| 版本串没变 | 用的是 `sg_cco` 目标（不注入 ECU 版本），或没带 `ECU_VERSION` |
| 升级包被模块拒（0x8007） | 烧了 CCO 族包；换 `out/sg_fusion_cco/…upg.bin` |
| 想整包烧（板子起不来） | 用 `image/…_image.fwpkg` + BurnTool；**先停 8765 释放串口** |
| 构建产物被 `make clean` 清掉 | 海思 GW 用 `scripts/build.sh clean`，只清 SDK 输出；不要跑模块工程的 `make clean` |
