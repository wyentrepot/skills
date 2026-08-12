---
name: cco-loghooks-scan
description: 扫描 CCO 固件源码中的日志/打印语句（LOG* 宏 / LOG_PRINTF / printf），采集为结构化清单（file/line/func/raw_format/params/parsable/direction/periodic/category/scope/province/anchor），作为运行状态钩子规则（loghooks）的数据来源。适用于为 loghooks 规则规划/判定提供打印语句清单、按功能归并、按省份（DI_QU_MODE）区分、标高频轮询噪音等场景。工程侧只做诚实采集，不改任何代码。
---

# CCO 固件日志打印扫描（loghooks 数据源采集）

## 适用场景

需要从 CCO 固件源码**采集所有日志打印语句**，输出为结构化清单，供运行状态钩子规则（loghooks）的规划与判定使用。典型触发：

- 生成 `序列号 | info | xxx.c (行号) | 消息` 这类模块日志的打印语句清单
- 扫描结果要按功能归类（join/collect/send/beacon/state/error/flash/other）、按省份（`DI_QU_MODE`）区分、标注高频轮询噪音
- 需要把打印语句转成 loghooks 规则（`match` 正则、`capture` 参数、`sequence` 状态流、`correlate` 锚点）的**数据来源**

**边界**：本技能只做**诚实采集与标注**，不改任何代码；规则转换与判定由 loghooks 本侧完成。

## 输出落点（必须遵守）

扫描结果写到指定输出目录（由环境变量 `CCO_OUT` 指定），一次扫描产出一个文件集：

| 文件 | 内容 |
|------|------|
| `cco_print_scan.json` | 全量结构化清单（JSON 数组，全字段） |
| `cco_print_scan.md` | 同源 Markdown 表格 |
| `cco_print_scan_summary.md` | 按功能归类汇总 + 疑问/不确定项 |
| `cco_print_scan.raw.json` | 中间原始产物（未分类，可留作证据/复跑底稿） |

> ⚠️ 若运行在被 E-SafeNet 透明加密的环境，确认写出的文件是**明文**（无加密头/LOCK/NUL），否则需按项目既定通道（git 明文）落盘。

## 运行方式

脚本目录**不要写死路径**，通过环境变量或命令行参数注入：

```bash
# 一键运行（3 步：提取 → 分类 → 汇总）
bash <技能目录>/scripts/run_scan.sh <CCO源码根目录> <输出目录>

# 或分步（环境变量注入）
export CCO_SRC=<CCO源码根目录>   # 例: /home/H_CCO/001/cco
export CCO_OUT=<输出目录>         # 例: /mnt/d/zzt/loghooks/rules_source
python3 <技能目录>/scripts/extract_logs.py    # 1. 机械提取
python3 <技能目录>/scripts/classify_logs.py   # 2. 语义分类
python3 <技能目录>/scripts/summarize_logs.py  # 3. 生成汇总
```

## 三条流水线

### 1. 机械提取（extract_logs.py）

- 扫描业务目录下的 `.c` 文件（APS/NWK/MAC/PHY/app 等），识别日志宏：`LOG_INFO/ERR/WARN/OK/FAIL/DBG/RAW/HEX/HEXDUMP/IP6ADDR/LONGADDR` 及 `LOG1_`/`LOG2_` 变体、`LOG_PRINTF`
- 每条记录：`file/line/func/raw_format/msg/params/parsable/direction/trigger/periodic/category/scope/province/anchor/context_lines/uncertain`
- 支持**多行 LOG 调用**（括号跨行）、**行内注释剥离**、**函数名定位**（花括号配对 + 多行签名兜底）
- **省份上下文**：跟踪 `#if DI_QU_MODE == XXX`（含 `||` 复合条件、`#elif/#else/#endif`），标 `scope=province` + `province=xxx`；复合省份记 `"chong_qing_mode,hu_nan_mode"`（**任一省份满足，非两者都满足**）

### 2. 语义分类（classify_logs.py）

- `category`：join / collect / send / beacon / state / error / flash / other
- `direction`：RX / TX / EVENT / unknown
- `periodic`：高频轮询噪音（`wait_times`/`Ts`/`trycnt`/`#wait Mut`/`get_order_phase`/`select_cco_ntb` 等）
- `parsable`：含 printf 转换符或标签化值或实参 → 可正则捕获
- `anchor`：跨来源关联的业务标识（ADDR/TEI/NID/MAC/TASK/SSN/PHASE/SEQ/SNID）
- `context_lines`：同函数内相邻日志行号（供组装 sequence 状态流）
- **权威标注表 `AUTHORITATIVE`**：按 `(文件, 函数)` 硬编码关键业务流（STA 入网 / MCLT 采集 / 上报状态机 / 注册 / 升级 等），命中优先，否则关键字兜底。**新项目/新流程请扩展此表**

### 3. 汇总报告（summarize_logs.py）

- 总量概览 + 按功能归类表（通用/省份分列）+ 省份分布 + 高频噪音清单 + sequence 状态流候选 + 疑问/不确定项

## 每一条打印语句的字段

| 字段 | 含义 | 必填 |
|------|------|------|
| `file` | 源文件（相对源码根，如 `protocol/aps/src/aps_ioctrl_nwk.c`） | ✅ |
| `line` | 打印语句所在行号 | ✅ |
| `func` | 所在函数名 | |
| `macro` | 使用的日志宏（LOG_INFO 等） | |
| `raw_format` | 打印原文格式（带引号） | ✅ |
| `msg` | 消息文本（去掉序号/文件前缀后的实际内容） | ✅ |
| `params` | 携带的变量/参数（参数名 + 语义，如 `cnt → 入网节点数`） | ✅ |
| `parsable` | 是否含可被正则捕获的可解析标识/数值 | ✅ |
| `direction` | RX / TX / EVENT / unknown | ✅ |
| `trigger` | 触发场景描述 | ✅ |
| `periodic` | 是否周期性/高频轮询 | ✅ |
| `category` | 功能归类 | ✅ |
| `scope` | `common` / `province` | ✅ |
| `province` | 若 scope=province，注明省份（如 `an_hui_mode`） | 条件 |
| `anchor` | 可作跨来源关联锚点的业务标识（NID/MAC/TEI/冻结时刻等） | |
| `context_lines` | 同流程前后打印行号（规划 sequence 状态流） | |

## 规则转换消费方式（供 loghooks 本侧，不需执行）

- **去噪**：剔除 `periodic=true` 高频轮询行（或转 `exclude` 过滤）
- **归类**：`category/scope/province` 直接落到规则文件对应字段
- **可解析性**：`parsable=true` 的 `raw_format` → 转正则 `match` 规则，`params` → `capture`；`parsable=false` 的仅作事件标记或跳过
- **状态流**：`context_lines` 多步骤流程 → 组装 `sequence` 规则
- **锚点**：`anchor` → 跨来源关联 `correlate` 的锚点
- **写入**：common 进 `loghooks/rules/common.json`，省份进 `loghooks/rules/provinces/<省>.json`
- **闭环**：拿真实日志跑 `loghooks scan` 核对命中率，不匹配回退补 `raw_format`/`uncertain`

## 常见问题与边界

1. **不要臆造**：只记录源码里真实存在的打印；不确定的标注 `uncertain` 并说明
2. **多行调用**：`LOG_INFO("...",\n  arg1,\n  arg2);` 已支持；若仍有遗漏检查括号配对
3. **`LOG_RAW` 多行拼接**：拓扑树打印（`assoc.c print_bind_topology` 等）用多条 `LOG_RAW` 拼一行，单条不完整需整段拼接后解析
4. **函数归属缺失**：签名跨 100+ 行（如 `cal_phase_arrange`）可能漏识别，人工补
5. **复合省份条件**：`province="chong_qing_mode,hu_nan_mode"` 表示任一省份满足
6. **`raw_format` 含 `__func__`**：转正则时 `%s` 位置会捕获函数名，需注意
7. **`LOG_HEX`/`LOG_HEXDUMP`**：16 进制 dump（MAC/TEI/帧负载），需按 `raw_format` 展开成连续 hex 正则
8. **省份宏包裹的公共功能**：`hu_nan_mode` 下常见 `rx_13762_*` 主机命令/`sta_auth_state`/`_config_scheme_prase`，需人工确认是省份特有还是公共功能被省份宏包裹

## 功能归类 category 参考

| 值 | 含义 |
|----|------|
| `join` | 入网（新节点/STA 入网/onnet 计数/关联/黑名单/注册） |
| `collect` | 采集上报（抄表/分钟采集 MCLT 上报/数据读取） |
| `send` | 往网络层发送/上行/转发 |
| `beacon` | 信标/网络发现/NID/相线 |
| `state` | 状态机/心跳/周期性状态 |
| `error` | 错误/异常/失败 |
| `flash` | 烧录/升级/flash 读写 |
| `other` | 其他（注明具体功能） |
