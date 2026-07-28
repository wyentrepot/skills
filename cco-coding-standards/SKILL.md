---
name: cco-coding-standards
description: CCO/STA 嵌入式 C/C++ 编码规范（142 条规则）及代码修改约定。适用于编写或修改 C 代码、修复编译错误、重构代码等场景。
---

# CCO/STA 编码规范

## 使用方式

加载此 skill 后，读取 `/home/rule/project-index/cco/coding-standards.mdc` 获取完整规范。

## 要点

- **最小 diff**：以最小变更解决问题
- **C89 标准**：严格遵守 C89，禁止 C99+ 特性
- **匈牙利命名**：`u8`/`u16`/`u32`/`i8`/`i16`/`i32` 等前缀
- **函数 ≤200 行，文件 ≤2000 行**
- **缩进 4 空格，行宽 ≤80 字符**
- **结论必须使用中文**
