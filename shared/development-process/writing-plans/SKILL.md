---
name: writing-plans
description: Use when an approved design, specification, or requirements describe a multi-step implementation task and a concrete execution plan is needed before modifying code.
---

# Writing Plans

Produce an implementation plan another engineer can execute without hidden context.

## Plan contract

Start with the goal, architecture, environment constraints, and exact files to create, modify, and test.

For every independently verifiable task include:

1. Exact file paths and responsibilities.
2. Inputs, outputs, interfaces, and dependencies.
3. A failing test or observable pre-change check.
4. The exact command and expected failure.
5. The minimal implementation change.
6. The exact verification command and expected success.
7. A review checkpoint before dependent work.

## Quality rules

- Use checkbox steps and keep each step to one action.
- Show complete commands, expected outputs, and necessary code shapes.
- Do not use `TODO`, `TBD`, "implement later," or vague placeholders.
- Do not reference an undefined function, type, file, or later task.
- Preserve user changes and identify destructive or external actions.
- Include rollback or failure handling when the task is risky.

Before handoff, check every requirement against a task, scan for placeholders and contradictions, and confirm names and interfaces are consistent.
