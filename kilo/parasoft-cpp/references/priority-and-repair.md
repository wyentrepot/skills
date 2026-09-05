# Priorities And Repair

## First-Level Findings

| Rule | Root concern | Safe repair approach |
|---|---|---|
| `BD-PB-NOTINIT-1` | Indeterminate read | Initialize at declaration or ensure assignment dominates every read, including members and array slots. |
| `BD-PB-NP-1` | Null dereference | Validate the pointer at the API boundary or before the dereference; define the error path. |
| `BD-PB-ARRAY-2` | Out-of-bounds access | Validate index and extent, account for signed negative values, and use strict upper bound `< count`. |
| `APSC_DV-003235-c-2` | Ignored error information | Check the result and return, recover, retry, or clean up according to the API contract. |
| `MISRA2004-10_1_a-3` | Signed/unsigned implicit conversion | Choose compatible types, use correctly suffixed constants, and validate before an unavoidable explicit conversion. |
| `MISRA2004-10_1_d-3` | Narrowing implicit conversion | Keep values in the wider type or validate the target range then explicitly convert. |
| `MISRA2004-10_1_g-3` | Argument implicit conversion | Match the callee parameter type or validate then explicitly convert at the call boundary. |
| `MISRA2004-11_3_a-3` | Pointer/integer cast | Redesign to retain the pointer type; only use `intptr_t`/`uintptr_t` for unavoidable representation-preserving interfaces. |

## Severity Policy

The source policy says to analyze and repair level 1 first, select level-2 rules by project need, and evaluate level-3 rules for new development. Treat memory safety and error handling as semantic changes requiring focused tests. Keep style-only fixes separate.

## Review Checklist

- Check all error and cleanup paths after adding validation.
- Confirm a new guard does not leak, double-free, skip locks, or alter required side effects.
- Verify casts use fixed-width or interface-defined types as required by the codebase.
- For pointer-to-integer use, confirm the target type is pointer-width and no truncation occurs.
- Run the smallest relevant build/test scope, then report unverified paths.
