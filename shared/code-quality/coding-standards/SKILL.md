---
name: coding-standards
description: Apply the internal embedded C coding standards when creating, modifying, refactoring, or reviewing .c and .h files, HAL, OSAL, drivers, middleware, and firmware. Use for C code changes or reviews that require minimal diffs, consistency with the module's existing C89/C99 style, naming and formatting compliance, correct function and control-flow design, complete cleanup on every error path, safe pointer handling, or embedded portability rules.
---

# 嵌入式 C 编码规范

## 核心约定

- 以最小变更解决问题，不移动或格式化无关代码。
- 使用文件或模块已有日志接口、类型定义、条件编译和 include 风格。
- 不执行 C89 与 C99 之间的语言版本迁移；新增代码与所在模块保持一致。
- 把标为“强制执行”的条款作为不可跳过的检查项。
- 只加载与当前任务相关的参考模块，不默认读取完整142条维护底稿。

## 按需加载

根据任务信号读取一个或多个模块：

- 头文件、include、注释、缩进、空格、括号、换行或代码长度：
  读取 [`references/formatting.md`](references/formatting.md)。
- 新增、重命名或审查函数、参数、变量、常量、枚举和全局符号：
  读取 [`references/naming.md`](references/naming.md)。
- 修改函数实现、变量、语句、宏、控制流、共享数据或返回值：
  读取 [`references/functions.md`](references/functions.md)。
- 涉及错误返回、异常状态、指针、动态内存、句柄、锁、提前返回或清理路径：
  必须读取 [`references/error-resources.md`](references/error-resources.md)。
- 涉及 HAL、OSAL、驱动、寄存器、`volatile`、定长类型、数值计算或内存策略：
  读取 [`references/embedded.md`](references/embedded.md)。

## 组合规则

- 仅改注释或排版时，只读取格式模块。
- 新增或修改普通函数时，读取函数模块；引入新标识符时再读取命名模块。
- 函数含指针、失败分支或资源获取时，同时读取函数模块和异常资源模块。
- 修改驱动、HAL 或硬件相关代码时，读取嵌入式模块，并按实际代码叠加函数、命名或异常资源模块。
- 执行全面规范审查时，读取全部五个模块。
- 只有维护规则库、核对来源或用户明确要求完整规范时，才读取
  [`references/coding-standards.txt`](references/coding-standards.txt)。

## 执行流程

1. 检查目标文件、构建配置和同目录代码，确认当前模块的实际风格。
2. 按任务信号加载最少必要的参考模块。
3. 检查修改代码及其成功、失败、提前返回和清理路径。
4. 实施最小必要改动，不顺带修正范围外的历史违规。
5. 运行工程已有的构建、静态检查或测试；无法运行时明确说明。
6. 汇报改动、验证结果、已加载的规范模块和仍存在的规则偏差。

## 冲突与偏差

- 优先服从用户对当前任务的明确要求和项目实际编译约束。
- 不静默违反强制规则；无法遵守时，说明具体规则、原因、影响和替代措施。
- 第三方代码或遗留代码按规范添加对应标记，除非任务明确要求修正。
- 不把建议规则描述为强制规则。
