---
name: coding-standards
description: Apply the internal embedded C coding standards when creating, modifying, refactoring, or reviewing .c and .h files, HAL, OSAL, drivers, middleware, and firmware. Use for C code changes or reviews that require minimal diffs, consistency with the module's existing C89/C99 style, naming and formatting compliance, complete cleanup on every error path, and safe pointer initialization, null checking, and post-release nulling.
---

# 嵌入式 C 编码规范

## 核心要求

在编写、修改或审查嵌入式 C 代码前，读取
[`references/coding-standards.txt`](references/coding-standards.txt)。
以最小变更满足需求，并把标为“强制执行”的条款作为不可跳过的检查项。

## C 语言风格

- 不执行 C89 与 C99 之间的语言版本迁移。
- 优先检查构建选项、同目录代码和目标文件现有写法。
- 允许沿用工程已采用的 C89 或 C99 风格，包括注释形式、变量声明位置、定长类型和数学接口。
- 新增代码与所在文件保持一致；不要仅为统一语言版本或个人偏好修改无关代码。
- 无法确认时，采用更保守且能被当前工程编译器接受的写法。

## 执行流程

1. 检查 `.c`、`.h` 文件及构建配置，确认当前模块实际采用的 C 语言风格。
2. 完整读取规范，并区分强制规则与建议规则。
3. 检查拟修改代码及其错误、异常、提前返回和清理路径。
4. 实施最小必要改动，不顺带格式化或重构无关代码。
5. 运行项目已有的构建、静态检查或测试；无法运行时明确说明。
6. 汇报改动、验证结果和仍存在的规则偏差。

## 强制资源安全检查

### 8.4 异常处理需要正确释放资源

- 枚举当前函数获取的内存、文件、套接字、锁和系统句柄。
- 覆盖成功、失败、异常、提前返回和部分初始化路径。
- 按获取顺序的逆序释放资源。
- 使用统一清理出口或等效机制，避免遗漏错误分支。
- 确保分配到一半即失败的部分初始化路径也能释放已有资源。
- 不用仅记录日志但不清理资源的分支掩盖泄漏。

### 8.5 避免指针引发的异常

- 定义指针时立即赋有效地址或 `NULL`。
- 解引用、内存访问或传给要求非空的接口前检查非空。
- 释放指针拥有的资源后立即置空。
- 检查别名和所有权，避免重复释放、释放后使用和悬空引用。
- 明确指针所有权，避免多个位置重复释放同一资源。

## 冲突与偏差处理

- 优先服从用户对当前任务的明确要求和项目实际编译约束。
- 不静默违反强制规则；确实无法遵守时，指出具体规则、原因、影响和替代措施。
- 第三方代码或遗留代码按规范添加对应标记，除非任务明确要求修正。
- 不把建议规则描述为强制规则。

## 输出要求

- 修改任务：给出变更摘要、受影响文件和验证命令/结果。
- 审查任务：先列问题，按严重程度排序并给出精确位置。
- 涉及动态资源或裸指针时，明确说明 8.4 与 8.5 的检查结果。
