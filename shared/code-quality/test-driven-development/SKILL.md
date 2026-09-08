---
name: test-driven-development
description: Use when implementing a feature, bug fix, refactor, or behavior change. Requires a failing test or reproducible pre-change check before production code, followed by the smallest passing implementation and cleanup.
---

# Test-Driven Development

Follow RED → GREEN → REFACTOR.

## RED

1. Write one minimal test expressing the required behavior.
2. Run it before changing production code.
3. Confirm it fails for the expected missing behavior, not a setup or syntax error.

If it passes immediately, correct the test or identify an already-satisfied requirement.

## GREEN

1. Write the smallest production change that makes the test pass.
2. Run the focused test and the relevant surrounding suite.
3. Fix production code rather than weakening a valid test.

## REFACTOR

Only after tests pass: remove duplication, improve names and boundaries, keep behavior unchanged, and rerun tests.

## Test quality

- Test externally observable behavior.
- Use names that describe the expected result.
- Prefer real collaborators; mock only unavoidable boundaries.
- Add a regression test for every reproduced defect.
- Keep test-only hooks out of production interfaces.

Do not claim completion without fresh test output showing zero relevant failures.
