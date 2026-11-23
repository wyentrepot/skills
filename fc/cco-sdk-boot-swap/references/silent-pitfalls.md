# 静默坑清单（silent-pitfalls）

> 编译器全部不报。每条都有实证出处。换 SDK 后排查"编译全绿但上板不正常"按此对照。

## P1 新库按新头布局访问结构体（0004）

`htimer_t` 新头内嵌 `match[]/mat_op[]`，旧头编译调用旧 API 链接通过，上板卡死在初始化
（htmr_init/get_htimer 死循环）。**串口打点二分定位**。

## P2 厂家库引用未交付符号（0004）

`PLC_RG_EN` / `get_board_cfg`：库 .a 里 UND 符号，链接报 undefined。处置：nm 查符号表，
按厂家包内原样补定义（get_*_cfg 同形态补函数）。

## P3 "当地址用"的宏升级成函数（0006 发现，0004/0005 遗留同源）

新头把 `BOARD_CFG` 从地址直译宏改 `get_board_cfg()`（返回 SRAM 缓存指针）：
- 读语境（MEMCPY 源，全工程 6 处）语义正确；
- **写语境 2 处**（iap_flash.c:146 IAP 切槽、phy_sal.c:1629 RF 校准落盘）`(uint32_t)BOARD_CFG`
  = SRAM 0x3e16c，过不了 flash_write 地址下限校验 → **FLASH_PARA_ERR 静默失败**（只打 LOG）。
- 反汇编实锤：`jal get_board_cfg → mv a1,a0 → jal flash_write`（修复后应为 `lui a1,0xfe030`）。
- 上板为何没暴露：双槽切换 boot 自管槽位不依赖 app 写 active；RF 校准写入产线未实测。
- **教训**：宏升级成函数必须全量审查使用语境，读/写分列。修复=地址语境用 `BOARD_CFG_ADDR`。

## P4 logger.h 把 __LINE__ 编进二进制（0005）

行内 `#if 代次` 会让新代源文件行号位移 → 产物指纹漂移 → 字节门失效。
**解法**：文件级代次选择（`*_v2.c` 旧版逐字节 + Makefile 按代选 obj），新代源文件一字不动。

## P5 切代不 clean 复用旧 .o（0005/0006）

.d 只记编译当时头路径。切代后旧 .o 复用，静默出错代固件（症状：链接报 get_decrypt_key /
bsp_wd undefined）。**解法**：`.sdk_ver_stamp` 戳记自动清理；无戳记（首次）也要清——实测盲区。

## P6 bin2all 第三参丢失（0006）

Makefile `all` 内嵌 bin2all 只传两参 → SDK_VER 落 jump_set 位恒走新代 boot 门。
**解法**：内嵌调用补第三参 + 引号。

## P7 中断顶层入口被覆盖 + 硬件 match 从未配置（0007 实锤，最隐蔽）

**症状**：编译全绿，上电 `fact test wait..` 后 300ms 窗口永不超时（cnt_ms 冻结），业务全瘫。

**链路**（反汇编逐级核实）：
1. `request_irq(5, IRQ_HTMR, _isr_htimer, NULL)` 挂的自家函数是 HTMR **唯一**顶层入口——
   库自带全局分发器 `isr_htimer`（libos.a 导出符号）**不会被调**；
2. 新代适配时 `_isr_htimer` 被重写为"只轮询 12 通道注册矩阵"，注释假设"libdrv 按 mat_op[] 自分发"——假设错误；
3. tick 经 `start_htimer` 把回调写进 htimer idx=3/ch=0（全局通道 12），**不在 12 通道矩阵内**；
4. 1ms 中断来了，顶层轮询不命中 → `isr_ticktmr` 永不执行 → `cnt_ms` 冻结。
5. 同案：`bsp_htmr_cmp_start` 只写 struct match[]，硬件 match 寄存器（f1300310+idx*32+ch*4）
   从未配置——12 通道 MAC 定时器（CSMA/VCS/coordination）同样全瘫。

**修复**：恢复 feature 同构 intr_stat/imsk 全局轮询分发（cap+mat，tick 与 12 通道统一经
mat_op 分发）；cmp_start 补 `set_htimer_mat(idx, match, ch)`。
**底层 API 还在**：`set_htimer_mat / get_htimer_intr_stat / clr_htimer_intr_stat /
get_htimer_intr_imsk / get_htimer_point` 在 venus8m/libos.a 全部导出，只是新头未声明——
文件内 `extern` 补声明即可用，不必动 SDK 头。

**教训**：换 SDK 后**每个中断入口的完整分发链要逐级反汇编实证**（谁挂顶层 → 中断来了先进谁 →
回调注册在哪级结构/矩阵 → 硬件寄存器谁写）。"上层 API 封装了分发"是假设，不是证据。

## P8 boot 交付物被 git clean 清掉（0006 步骤 2）

boot 是 gitignore 未跟踪件，`git clean -xdf` 清掉后打包链 md5 硬门拦截（护栏正确生效）。
**解法**：从权威交付位 release/*/ 恢复并 md5 门验证。

## P9 厂测帧发错串口（0007 排查过程）

厂测帧（0xA5 头 + 非反射 CRC32 poly 0x04C11DB7）必须发对外通信口（uart1, 9600 8N1）；
打印口只出日志。帧格式：`A5 [1] [ctl] [len=2+data] [id_lo id_hi] ... + CRC32(前 len+4 字节)`。
误发打印口会被终端回显骗成"板子应答"。

## 反汇编速查（排查 P7 类问题时）

```bash
# 库函数语义核实
riscv64-unknown-elf-objdump -dr <lib>.a | awk '/<func>:/,/^$/'   # 函数体+重定位
riscv64-unknown-elf-objdump -t <lib>.a | grep <symbol>           # 符号导出/局部/UND
# 关注：R_RISCV_CALL（调了谁）/ f1300xxx（硬件寄存器窗）/ 结构体偏移（lw/sw 后缀数字）
```
