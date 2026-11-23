---
name: cco-sdk-boot-swap
description: Use when 需要给 CCO/STA 固件更换厂家 SDK 版本（换代 ver_03-00-02-08 ↔ ver_03-00-03-11 等）、更换 bootloader、双代 SDK 兼容编译（make cco_v3 / make cco / make ecu）、换 SDK 后上板验证或排查"编译全绿但上板卡死/不启动"类问题。例如"厂家发了新 SDK 包怎么换"、"新硬件要用新 SDK"、"切回旧代编译"、"换 SDK 后板子没反应"。
disable-model-invocation: true
---

# CCO 换 SDK / 换 Boot 指导（cco-sdk-boot-swap）

## Overview

一套代码树、两代 SDK 各自完整可编可跑。源自 H_CCO/002 四轮实证（0001 引脚适配 / 0002 砖板根因 / 0004 换 SDK / 0005 双代兼容 / 0006 重演审查 / 0007 中断分发缺陷）。

**核心原则：编译过 ≠ 适配对。** 链接器不报的静默差异（结构体布局、中断分发机制、宏升级成函数）必须靠"反汇编核分发链 + 上板打点"实证——**每个中断入口的完整分发路径都要逐级核实**。

## 按需加载（渐进式，用完即止）

| 任务 | 读 |
|---|---|
| 换 SDK 全流程（资产四层/步骤顺序） | references/swap-workflow.md |
| 双代兼容实现（影子树/SDK_VER/切代自洁） | references/dual-gen-build.md |
| 上板烧录与验证（boot 菜单/XMODEM/验收门） | references/onboard-verify.md |
| 静默坑清单（踩过的每一个） | references/silent-pitfalls.md |

## 十条铁律（跨场景）

1. **换代四层资产缺一不可**：库（4 个 .a）/ 头（41+，同名头先审计再决定换不换）/ lds+镜像标识（成对一致）/ 自有代码 API 调用点。
2. **旧库双落位保留**，不能只换不留。
3. **新代零扰动硬门**：加兼容层前后新代产物 md5 逐字节不变——这是重构安全网。
4. **boot 与镜像同代成套**：打包链按 SDK_VER 选 boot（md5 硬门两代各自生效），镜像标识（0xFC…旧/0x22…新）互挡是第二重防线。
5. **文件级代次选择**：改过的 BSP 文件新增 `*_v2.c` 逐字节保留旧版，Makefile 按代选 obj——logger.h 把 `__LINE__` 编进二进制，行内 `#if` 会破坏字节门。
6. **切代自洁**：`.sdk_ver_stamp` 戳记 + 变化自动清 `*.o/*.d`；无戳记（首次）也要清——实测盲区。
7. **中断分发链逐级实证**：request_irq 挂的顶层 handler 是唯一入口，库里同名分发器不会被调；回调注册进哪级矩阵要跟到硬件寄存器（见 silent-pitfalls §P7，0007 实证）。
8. **"宏升级成函数"必须全量审查使用语境**：读语境（MEMCPY 源）与写语境（flash_write 地址）语义不同，`(uint32_t)MACRO` 写语境会变成 RAM 指针被静默拒绝。
9. **每步保持"预期编译结果"声明**：不符即停——教学点常藏在预期不符里。
10. **上板验证用打点版先行**：probe 点 LOG_SYNC 编入 ELF 验证数量后上板，二分定位卡死点。

## 验收门速查

| 门 | 判据 |
|---|---|
| 新代零扰动 | 新代产物 md5 不变 |
| 旧代同口径 | 与换代前 feature 编译级对照（头标识/段布局） |
| 同代成套 | boot md5 门 + 镜像标识互挡 |
| 切代自洁 | 双向切换不手工 clean，产物各回基线 |
| 静默坑清零 | 新符号的宏级引用语境全量审查（读/写分列） |
| 上板四件 | 版本串 / flash 读写回环 / IAP 升级全程 / 120s 无复位 |

## 红线

- 换 SDK 前必做旧代资产指纹快照（库/lds md5），否则无法回溯验证。
- boot 是 gitignore 交付物，`git clean -xdf` 会清掉——打包前先从权威交付位（release/*/）恢复并过 md5 门。
- 板上双槽：保留一个回退槽（`active 0/1` 切换），新固件进非活动槽验证后再切。
- 编译目标命名与代次绑定要用户拍板后写进 REQS（0006 变更 2 口径：cco_v3=新代+V303 宏 / cco=旧代 / ecu=旧代+ECU 宏）。

## 项目锚点（H_CCO/002）

- 现行口径与指纹：`reqs/0006-sdk-swap-reviewed/DONE.md` + `steps/DIVERGENCE-TABLE.md`
- 静默坑完整案例：`reqs/0006-sdk-swap-reviewed/steps/`（step-2~step-6）+ `reqs/0007-facttest-hang/DONE.md`
- 交接总纲：`交接-CCO换SDK-20261015-v2.md`（遗留 3 项：厂家问项/业务回归/观察窗延长）
