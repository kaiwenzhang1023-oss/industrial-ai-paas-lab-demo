# RC3.4 Live Browser Closure — V4 Candidate (HOLD)

- Full source baseline: SHA256 `cbaa374b34a04fade28dc7dcc5ab19a9bc6dd39a86afe5ee0742bc0f332c2554`, 106 hashed files, unchanged from PG16 evidence.
- PG16 isolated enterprise gate: `PASS` (137 checks).
- Render candidate deployed commit: `638665eb2640818b323def120071b0036f80a0a7` (latest confirmed live).
- Prior browser V3: 13/14 checks PASS, failed What-if 422; core MRP/approval/worker/receipt/audit completed.
- V4 fix: Pydantic string quantity, material/stock derived from persisted snapshot, explicit JSON, response details, stage logs, screenshot inside active browser context, native A/B and tenant checks.
- Frozen RC2 branch: read-only SELECT verified **0/11 test Run IDs present**. This only proves those test Run IDs are absent; no claim of a full database content hash comparison.
- V4 actual live browser execution: **HOLD, not executed by this packaging step**.
- Final Release Gate: **HOLD**. Neither this ZIP nor offline compile creates a live PASS.
- Production and external ERP/MES/SRM: not written. Worker evidence is `INTERNAL_VALIDATION_ONLY`.

## Required final acceptance

Run `RUN_RC34_LIVE_BUSINESS_GATE_V4.ps1` exactly once from full-source root. Inspect `release_evidence/live_business/RESULT.json`. Promote release only after all V4 checks PASS and final evidence/signature review.

## V4 one-shot conclusion

The V4 PowerShell runner invokes the browser check and the non-mutating `RUN_RC34_FINAL_RELEASE_GATE_V4.py` verifier. The verifier currently reports source PASS, PG16 PASS, frozen branch test-run absence PASS, live V4 HOLD, and post-run Render verification HOLD. It must not claim overall release PASS before a genuine cloud result and independent commit check.
