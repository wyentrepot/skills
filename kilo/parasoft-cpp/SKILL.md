---
name: parasoft-cpp
description: Apply the organization's Parasoft C/C++ scanning rules when writing, reviewing, or repairing C/C++ code. Use for any C/C++ implementation, code review, Parasoft finding remediation, or static-analysis preparation, especially for memory safety, initialization, error handling, implicit conversions, pointer/integer casts, and the documented coding conventions.
---

# Parasoft C/C++

Apply the documented Parasoft baseline without changing behavior merely to silence a finding. Read `references/rules.md` before C/C++ code changes; load `references/priority-and-repair.md` for finding remediation or review.

## Workflow

1. Identify the language, build target, ownership/lifetime model, and the exact scanner finding when available. Treat the finding location as a clue, not proof.
2. Address first-level safety findings before style findings. Preserve API and ABI compatibility unless the user approves a breaking change.
3. Make the smallest behavior-preserving change that removes the root cause. Add bounds, null, range, and return-value checks where required; do not add unchecked casts, blanket suppressions, or dead code.
4. Compile and run focused tests when available. Re-run Parasoft or another relevant static analysis tool if present. Report any finding that needs project-specific intent rather than guessing.

## Mandatory Safety Rules

Prioritize these rules in every review and repair:

- `BD-PB-NOTINIT-1`: Initialize objects and every read array/struct member on all control-flow paths before use.
- `BD-PB-NP-1`: Establish non-nullness before dereference and retain the guard across intervening control flow.
- `BD-PB-ARRAY-2`: Validate indices and lengths; use `index < count`, never assume a caller's length is valid.
- `APSC_DV-003235-c-2`: Check and propagate, handle, or deliberately map error-returning function results. Do not discard them.
- `MISRA2004-10_1_a-3`, `MISRA2004-10_1_d-3`, `MISRA2004-10_1_g-3`: Make signedness, narrowing, and argument conversions explicit only after range validation; prefer correcting the type at the boundary.
- `MISRA2004-11_3_a-3`: Avoid pointer/integer conversion. Use `intptr_t` or `uintptr_t` only when an address-as-integer interface is unavoidable and supported, and preserve round-trip semantics.

## Repair Guardrails

- An explicit cast documents a deliberate conversion; it does not make overflow, truncation, sign change, invalid enum values, or null dereference safe. Check the value first where loss is possible.
- Do not automate broad renames, `const` changes, header include removals, formatting rewrites, or tab conversion together with semantic safety fixes. They cause noisy diffs and can break public APIs, macros, generated code, or build behavior.
- For a scanner warning with insufficient context, retain behavior and explain the missing invariant or request the report trace. Use a justified project-approved suppression only when remediation is inappropriate.
- Follow existing project conventions where they conflict with lower-priority style rules, unless the user asks for a migration.

## Rule Scope

Use `references/rules.md` for the complete documented set grouped by family. The source document is a working baseline, not the authoritative scanner configuration: its tables contain duplicate rows and a known priority-list typo (`BD-PB-NOTINIT-1` was once labeled as `BD-PB-ARRAY-2`). Prefer the actual Parasoft report and configured properties for rule identifiers, severity, and exceptions.

## Completion Report

State the rule IDs addressed, the invariant or behavior preserved, validation performed, and any findings deliberately deferred due to missing context or project policy.
