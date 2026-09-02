---
name: brainstorming
description: Use before creative implementation work when requirements are ambiguous or material design choices remain, such as choosing architecture, behavior, boundaries, or workflows. Do not use merely because a task changes code or configuration when the user has already specified the approach and success criteria.
---

# Brainstorming

Turn an idea into an approved design before implementation.

## Required workflow

1. Inspect the relevant project context, existing patterns, and constraints.
2. Identify the user goal, scope, success criteria, and important non-goals.
3. Ask one focused question at a time only when an unresolved decision materially affects the result.
4. Propose two or three viable approaches with trade-offs and a recommendation.
5. Present a design covering components, boundaries, data flow, errors, and verification where relevant.
6. Obtain explicit user approval only when the proposed design resolves material choices not already decided by the user.
7. After approval, use `writing-plans` for multi-step implementation.

## Design principles

- Keep scope minimal and omit speculative features.
- Follow existing project conventions unless the task requires changing them.
- Give each component one clear responsibility and a stable interface.
- Surface uncertainty and irreversible choices early.
- Do not treat a vague request as permission for consequential product decisions.

For a small, well-specified change with no material design choice, proceed without an additional approval gate.
