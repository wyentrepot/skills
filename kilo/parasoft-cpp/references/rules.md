# Documented Parasoft Rule Baseline

Use this as a concise routing reference. Consult the configured Parasoft rule documentation for exact analyzer semantics and exemptions.

## Application Security And Flow Analysis

- `APSC_DV-003235-c-2`: Test returned error information.
- `BD-PB-NOTINIT-1`: Avoid use before initialization.
- `BD-PB-NP-1`: Avoid null-pointer dereference.
- `BD-PB-ARRAY-2`: Avoid out-of-bounds array access.
- `BD-PB-VOVR-3`: Avoid values overwritten before use.

## AUTOSAR

- `AUTOSAR-M16_2_3-a-2`: Use multiple include guards.
- `AUTOSAR-A16_2_2-a-2`: Include only declarations/definitions required for compilation.
- `AUTOSAR-A6_6_1-a-2`: Do not use `goto`.
- `AUTOSAR-A2_7_2-a-2`: Do not comment out code.
- `AUTOSAR-A4_7_1-c-2`: Avoid lossy implicit integer-constant conversion.
- `AUTOSAR-A7_5_2-a-2`: Do not use recursion.
- `AUTOSAR-M5_2_10-a-2`: Do not mix increment/decrement with arithmetic in one expression.

## CERT C And Control Flow

- `CERT_C-EXP00-a-3`: Parenthesize or split expressions with lower-than-arithmetic-precedence operators.
- `CERT_C-MSC01-b-2`: Put `default` last in every `switch`.
- `CERT_C-PRE01-a-1`: Parenthesize each function-like macro parameter occurrence except `#`/`##` operands.
- `CERT_C-DCL00-a-3`: Declare unmodified local variables `const` where safe.
- `CERT_C-DCL00-b-3`: Declare unmodified parameters `const` where API-compatible.
- `CODSTA-34-3`: Use `typedef` for function-pointer declarations.
- `CODSTA-56-3`: End each `case`/`default` with explicit `break`, `return`, or documented fallthrough.
- `CODSTA-92-3`: Do not reuse standard-library macro/object names.
- `CODSTA-175_b-4`, `CODSTA-176_b-4`, `CODSTA-177-4`: Remove unused type, tag, and macro declarations when safe.

## Formatting, Documentation, And Metrics

- `COMMENT-02-3` to `COMMENT-05-3`: Copyright, file-introduction, function, and variable comments.
- `FORMAT-01-5`: Do not use tab characters; `FORMAT-06-3`: one statement per line.
- `FORMAT-07-3`, `FORMAT-08-3`, `FORMAT-11-3`, `FORMAT-12-3`, `FORMAT-17-3` to `FORMAT-22-3`, `FORMAT-24-3`, `FORMAT-27-3`: documented spacing and four-space indentation rules.
- `HICPP-5_1_3-a-3`: Parenthesize mixed-operator expressions; `HICPP-8_1_1-a-3`: avoid more than one pointer indirection in declarations.
- `JSF-001-3`: function logical lines <= 200.
- `METRICS-15-3`: at most five parameters; `METRICS-24-5`: source file <= 500 lines; `METRICS-26-3`: line length <= 120; `METRICS-34-5`: essential complexity <= 4.

## MISRA Conversions And Declarations

- `MISRA2004-10_1_a-3`: signed/unsigned integer implicit conversions.
- `MISRA2004-10_1_b-3`: integral-to-floating implicit conversions.
- `MISRA2004-10_1_c-3`, `10_1_f-3`, `10_1_i-3`: implicit conversion in complex expressions.
- `MISRA2004-10_1_d-3`: wider-to-narrower implicit conversions.
- `MISRA2004-10_1_e-3`: implicit conversion in function return expressions.
- `MISRA2004-10_1_g-3`: implicit conversion in function arguments.
- `MISRA2004-10_2_a-3`, `10_2_b-3`: floating-to-integral and wider-to-narrower floating implicit conversions where enabled.
- `MISRA2004-11_3_a-3`: do not cast pointers to integer types.
- `MISRA2004-6_3_b-3`: use explicitly sized integer typedefs instead of standard signed/unsigned integer type names where project policy applies.
- `MISRA2004-8_5-3`: do not define objects/functions in headers.
- `MISRAC2012-RULE_13_2-f-2`: do not access more than one volatile object between adjacent sequence points.

## Naming And Preprocessing

- `NAMING-01-3`: uppercase `#define` constants.
- `NAMING-05-3`: local variables begin lowercase.
- `NAMING-10-3`: named types, structs, typedefs, enums begin uppercase.
- `NAMING-17-3`: function names begin uppercase.
- `NAMING-33-3`: identifiers do not begin `_` or `__`.
- `NAMING-45-3`: do not distinguish identifiers only by case, underscore, or confusable characters.
- `NAMING-HN-38-3`: static variables follow the project's Hungarian naming convention.
- `PREPROC-29-3`: include standard headers with angle brackets.
