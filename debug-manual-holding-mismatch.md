[OPEN] manual holding mismatch

## Context
- Symptom: Manual holding input `026633`, amount `14632`, profit `1877` is submitted, but the rendered holding value becomes much larger than expected.
- Expected: After manual submission, displayed holding amount and profit should stay aligned with the user-entered amount/profit basis.

## Hypotheses
1. Frontend converts amount/profit into shares using the wrong nav source or wrong timing.
2. Manual add path is appending to an existing holding instead of replacing it.
3. Backend stores correct values, but frontend recomputes display amount/profit using stale valuation fields.
4. Existing holding data for the same fund already exists, so the new manual input is merged on top of prior shares/cost.

## Plan
1. Inspect current manual-add path.
2. Add instrumentation only.
3. Reproduce with the reported fund code and values.
4. Identify confirmed hypothesis and then apply a minimal fix.
