# RC3.4 PG16 Enterprise Integration Gate — Candidate Handoff

**Status before user execution: NOT RUN / HOLD.** This package contains the live isolated-PG16 harness; no new live database PASS is claimed.

## Baseline and protection
- Development baseline: RC3.4 complete candidate work tree.
- Version A V1.9 and Version B RC2 remain frozen.
- Existing Neon isolated branch only: `v19b-ux-rc31-isolated-acceptance` / endpoint `ep-twilight-violet-bb8pm1v6` / database `industrial_v19b_preview`.
- No Docker container, Neon branch, database, schema or migration is created.
- No Render deployment is performed by this PG16-only script.

## Live PG16 coverage implemented
1. PostgreSQL 16/schema/seed preflight and strict endpoint allowlist.
2. API 401/403/404 matrix across viewer, planner, approver, operator and admin identities.
3. Cross-tenant run/workflow/overview/What-if/command isolation.
4. Concurrent duplicate approval, idempotent replay, conflicting payload rejection and exact persisted decision/outbox/audit counts.
5. Worker application-failure injection → RETRY → successful DONE, no premature receipt, single internal receipt and audit trail.
6. Two concurrent workers over two pending jobs using PostgreSQL `FOR UPDATE SKIP LOCKED`.
7. Lease expiry/reclaim and rejection of stale worker acknowledgement.
8. Dynamic Version A native RC8 JavaScript vs Version B persisted PG16 comparison for scenarios A/B/C/D, with identical input hashes and per-difference explanations.
9. Stock/receipt/due What-if checks with per-run PG16 table hashes before/after.
10. Statement timeout cancellation and fresh-connection recovery.
11. Source `mock_erp`/`mock_wms` tables hash unchanged before/after.

## Important interpretation
- This tests API-layer authorization. It does not claim PostgreSQL native RLS policies.
- Worker failure injection is a controlled application-level failure and lease expiry, not a Neon compute/node outage.
- Worker receipts remain `INTERNAL_VALIDATION_ONLY`; no external factory system is called.
- A/B `DIFFERENT` is preserved as a real business discrepancy with explanations; same-snapshot comparison PASS does not imply result parity PASS.
- Scenario C remains a customer due-date postponement; D remains a BOM usage anomaly.

## Local verification performed for this package
- `python -m pytest -q tests`: 29 passed.
- `python -m py_compile tests/enterprise_pg16_gate.py`: passed.
- `node --check enterprise_workbench/site/enterprise-console.js`: passed.
- Actual Neon PG16 integration gate: **not executed by assistant**; requires the user's secure connection to the existing isolated Neon branch and explicit write acknowledgement.

## User action
Run only `RUN_RC34_PG16_ENTERPRISE_ONLY.ps1` from the source root. It prompts for the Neon connection string using hidden input, checks the exact endpoint/database allowlist, and requires the confirmation phrase `RUN_ISOLATED_PG16_TESTS`.

Evidence: `release_evidence/pg16_enterprise/RESULT.json` and `WHAT_IF_*_BEFORE/AFTER.json`.
