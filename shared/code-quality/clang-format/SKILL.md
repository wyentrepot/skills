---
name: clang-format
description: Use when creating, reviewing, modifying, troubleshooting, or applying `.clang-format` rules; analyzing C, C++, Objective-C, Java, JavaScript, or related code style; minimizing formatting diffs; or integrating clang-format with editors, hooks, and CI.
---

# clang-format

Use repository evidence and the installed clang-format version. Do not invent style rules or mass-format without authorization.

## Workflow

1. Locate the nearest `.clang-format` or `_clang-format` and identify its scope.
2. Run `clang-format --version`; options vary by release.
3. Inspect representative files and existing conventions.
4. Decide whether to preserve style, repair rules, or establish a baseline.
5. Make the smallest configuration change that addresses the request.
6. Preview before writing:

```bash
clang-format --style=file path/to/file.cpp | diff -u path/to/file.cpp -
clang-format --dry-run --Werror --style=file path/to/file.cpp
```

7. Test files exercising relevant braces, indentation, includes, alignment, wrapping, comments, templates, and macros.
8. Apply `clang-format -i --style=file` only within the approved scope.
9. Review the diff and remove unrelated whitespace churn.

## Configuration guidance

- Start from an appropriate `BasedOnStyle`; override only intentional differences.
- Use `clang-format -dump-config` to inspect supported options.
- Keep language-specific sections explicit.
- Preserve `// clang-format off` and `// clang-format on` regions.
- Treat generated, vendored, third-party, and macro-heavy files cautiously.
- Pin or document the clang-format version in CI when reproducibility matters.

If target files live in WSL, use `wsl-safe-writing` for mutation and verification.
