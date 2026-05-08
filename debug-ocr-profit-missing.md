[OPEN] OCR profit missing

## Context
- Symptom: OCR upload succeeds, but recognized holdings show `0.00` for holding profit or fail to recognize holdings from a valid screenshot.
- Expected: OCR should extract row-level holding profit when present and return it to the confirmation modal.

## Hypotheses
1. OCR raw text does not contain the holding-profit column for this screenshot style.
2. Backend row-profit extraction filters out valid numeric profit blocks.
3. Backend returns `profit`, but frontend mapping/rendering drops it.
4. The UI is connected to an outdated backend process or stale route.

## Plan
1. Reproduce with runtime evidence.
2. Add instrumentation only.
3. Confirm or reject hypotheses.
4. Apply minimal fix after evidence.

## Evidence
- Reproduced with `backend/uploads/ocr/20260507155854_IMG_8133.png`.
- Debug server logs show `block_count = 86`, `deduped_count = 11`.
- For each detected row, `profit` is populated but `amount = 0.0`.
- Final `candidate_count = 0`, so upload raises empty-result error.

## Hypothesis Status
- H1 rejected: OCR raw blocks are present.
- H2 confirmed: amount extraction path is filtering/missing valid amount blocks.
- H3 rejected: response serialization is not the first failure point.
- H4 rejected: reproduction happened on latest backend process `8002`.
