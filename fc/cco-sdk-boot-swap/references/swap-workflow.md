# 换 SDK 全流程（swap-workflow）

> 来源：0004（首次换代）+ 0006（重演式审查，9 步逐提交重做）。按此顺序执行，每步有达标线。

## 前置：基线冻结

1. 旧代资产指纹快照：4 个库（libos/libcpu/libphy/libcrypto）+ lds，md5 落盘。
2. 从换 SDK 前基线 commit 切新分支。
3. `make cco`（旧代基线）全绿 ×2，记录 iap md5 作为回溯锚点。
4. boot 是 gitignore 交付物：先确认 `make/boot/boot_venus8m_riscv.bin` 在位并过 md5 门
   （实测被 `git clean -xdf` 清掉过，从 release/ 权威位恢复）。

## 换代顺序（0006 验证的 9 步精编）

| 步 | 内容 | 达标线 | 坑 |
|---|---|---|---|
| 0 | 基线冻结（上） | iap md5 双构建一致 | — |
| 1 | 板级引脚宏（如 CCO_BOARD_V303） | 全绿，新宏零行为变化 | 引脚互换只动 .pins/mux，不动逻辑 |
| 2 | 库+头整体换新（厂家包拍平落位） | 编译全绿或预期报错 | 真卡点常在打包链 boot 门而非编译 |
| 3 | 配套头补齐 + API 签名适配 | 全绿 | 新库按新头访问结构体，旧头编译零告警但上板卡死 |
| 4 | 黑名单/存储区地址适配 | 全绿 | 存储区地址随 flash 布局变 |
| 5 | 旧代影子树落位 | 逐文件 md5 全等 feature | 混入构建残留要清 |
| 6 | Makefile SDK_VER 双代参数化 | 三目标全绿 + 切代矩阵 | 旧代链接缺符号→flash.h 宏按代分叉 |
| 7 | 打包链按代选 boot | 打包矩阵全过 | bin2all 缺第三参会落错 boot |
| 8 | 总审 | 分歧总表四类归档 | — |
| 9 | 交付 | readme 四要素 + 烧录记录表 | — |

## 头文件处置细则（19 头审计经验）

- 厂家包结构 ≠ 工程结构：按包内 include 路径拍平落位（如 types.h 按 uart.h 的 include 路径落）。
- 同名头未必该换：
  - `list.h` 有受控本地补丁 → 保留本地版 + 受控补丁重放；
  - `sha1.h` 同名异物（非对应物）→ 不换。
- 全量头差异先出 QA 清单（65 对头对照），再逐个拍板。
- 厂家库引用未交付符号（PLC_RG_EN / get_board_cfg）：`nm` 查库符号表发现，按厂家包内原值补定义。

## API 适配模式（0004/0005 实证）

- htimer：旧 mat+clr+enable_isr 三件套 → 新 `start_htimer` 五参（TMR_PERIODIC, timeout, isr, arg）；
  match[]/mat_op[] 内嵌进 htimer_t，由分发器读结构体回调。
- gpio：上下拉改双参 `(pins, en)`。
- ticktimer：start_htimer 五参周期模式挂 isr。
- 签名变化是体力活；**静默行为差异编译器不报**（见 references/silent-pitfalls.md）。

## 重演式审查法（0006 验证，适合审计/教学场景）

- 逐提交重做（非 cherry-pick），每步 `git diff 本步 原参照` = 0 为树级达标线。
- 每步先发审核单（目的/文件清单/编译管控/IO 变动/风险回退）→ 用户批准 → 实施 → 实况落盘 `steps/`。
- commit message 沿用原提交原文（工程风格），考据细节只落 steps/ 文档。
- 终了出 DIVERGENCE-TABLE（vs 基线，四类归档：厂家资产/影子树/构建层/自有代码）。
