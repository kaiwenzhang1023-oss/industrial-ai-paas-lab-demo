# Version B RC3.4 — Scenario-integrated candidate (NOT RELEASED)

## Source baseline

RC3.3 Business-First full source. Version A and frozen Version B RC2 unchanged.

## Implemented

- `POST /api/v1/version-b/enterprise/mrp/runs` accepts an optional JSON body `{ "scenario": "A" | "B" | "C" | "D" }`; no body remains compatible and defaults to A.
- A: source unchanged. B: in-memory removal of available stock and receipts for the first purchased BOM component. C: customer due dates postponed seven days (NOT a finite-capacity production delay). D: first BOM component quantity doubled as a flagged abnormal-consumption case (NOT a broken BOM mapping).
- Source tables remain read-only during overlay, retaining the existing transaction, input hash, source fence and run/tenant registration. Scenario provenance stored in `platform.run_snapshot_fences.source_versions.scenario`, with original canonical snapshot preserved in `version_b_rc2.run_inputs`.
- Frontend scenario selector; snapshot-derived order count/IDs, shortage material count and purchased planned supply count. No invented monetary value: missing price is explicit.
- Frontend friendly errors; raw errors only in technical drawer; approval/dispatch state gate tightened; run identifier cached locally without credentials.

## Critical limitations and pending work

- **No live PG16 E2E has been run** on this candidate. Docker/Render/Neon unchanged.
- Browser refresh only recovers non-sensitive run ID; it CANNOT recover access to old tenant without its original valid signed session. Session tokens are intentionally not persisted. A secure server-backed resume flow is needed for full restoration.
- Scenario C is due-date delay, not MES capacity-driven production delay. Scenario D is abnormal BOM quantity, not a real broken cross-system mapping. Those need additional domain contracts if full scenario fidelity is required.
- The business scenario overlay does not mutate shared ERP/WMS/BOM source data. It is a demonstrable simulated source-change, persisted as an immutable PG16 run snapshot.
- RC3.3 browser tests include obsolete assertions forbidding *any* localStorage and assuming old 5-tab view; those tests must be revised to RC3.4 contracts, not presented as PASS.
- Historical RC2 test coverage and live end-to-end cloud acceptance still required.
- No delete/reset tenant endpoint: audit evidence is immutable. Use new run to replay.
- No pricing table: estimated procurement amount is shown as unavailable, never fabricated.

## Gate run (local)

`PYTHONPATH=backend:. python -m pytest -q tests/test_rc34_scenarios.py tests/test_preview_rc2.py`

`node --check enterprise_workbench/site/enterprise-console.js`

## Deployment

Do not deploy until review and full regression. Use GitHub Desktop to update the existing continuous candidate branch; only after source and integration gates, manually deploy the same Render candidate service. Do not alter Version A, RC2 branch or RC2 Render/Neon.
