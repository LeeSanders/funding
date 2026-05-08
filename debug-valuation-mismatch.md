[OPEN] valuation mismatch

## Context
- Symptom: Portfolio real-time valuation appears inaccurate; daily estimated profit and percentage look suspicious.
- Expected: Today's estimated profit amount and percentage should align with the selected valuation source and holding size.

## Hypotheses
1. Backend `estimated_change_rate` is inflated or sourced incorrectly.
2. Backend `estimated_profit` uses the wrong calculation base.
3. Frontend display logic applies an incorrect derived formula.
4. Fallback/proxy valuation is being used without clear distinction, causing misleading output.

## Plan
1. Read current valuation pipeline.
2. Add instrumentation only.
3. Reproduce with current holdings.
4. Identify confirmed hypothesis and then apply a minimal fix.

## Evidence
- Backend currently derives `latest_nav` and `estimated_change_rate` from `Data_netWorthTrend[-1]`.
- Runtime logs show the UI values exactly match backend-returned `estimated_profit` and `estimated_change_rate`.
- Eastmoney realtime valuation endpoint `https://fundgz.1234567.com.cn/js/<code>.js` returns materially lower intraday values:
  - `012895 -> gsz 1.2448, gszzl 1.95`
  - `017470 -> gsz 2.6990, gszzl 2.00`
  - `011609 -> gsz 1.2834, gszzl 1.32`
- Current backend returned for the same funds:
  - `012895 -> 3.50%`
  - `017470 -> 5.69%`
  - `011609 -> 5.45%`

## Hypothesis Status
- H1 confirmed.
- H2 rejected for now.
- H3 rejected.
- H4 partially confirmed.
