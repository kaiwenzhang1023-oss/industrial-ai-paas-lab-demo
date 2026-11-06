# Version B RC3.4 — Scenario semantics, browser regression and PG16 gate

## Status: SOURCE CANDIDATE / LOCAL PASS / CLOUD E2E HOLD

- Baseline: RC3.4 candidate, Version A and Version B RC2 frozen, no production resources modified.
- A: unchanged manufacturing sample; B: first purchased BOM component available stock and receipts cleared in an isolated in-memory overlay; C: customer order due dates shifted by 7 days (NOT finite-capacity production delay); D: first BOM line usage doubled (NOT broken BOM mapping). Scenario provenance is recorded in the immutable snapshot fence.
- Backend: existing POST /mrp/runs remains compatible with no body (A), optional {scenario:A|B|C|D}. Existing PG16 transactions, tenant scope, approvals, Outbox, Worker and audit are not rewritten.
- Local pytest: 16 passed, PYTHONPATH=backend:. python -m pytest -q tests.
- Headless Chromium Playwright: 12 checks passed in tests/browser_enterprise_rc33.py. Mocked HTTP only: initial navigation, state gates, summary, approval, Worker/receipt, reset, mobile, scenario POST A/B/C/D, rejected terminal state.
- JS syntax: node --check enterprise_workbench/site/enterprise-console.js PASS. Python compileall PASS.
- Neon PG16.15 isolated branch read-only check: schema_ready=true; 5 run, 5 decision, 5 outbox, 5 receipt records before deployment. Historical records are not evidence of RC3.4.
- Real RC3.4 cloud PostgreSQL E2E: HOLD. Candidate code has NOT been pushed or deployed, so claiming a live A/B/C/D flow would be false.
- Browser session limitation: localStorage holds non-sensitive run ID only. Auth token is memory-only, so refresh cannot restore access to the old tenant. Secure resume requires separate backend design; no cross-tenant bypass.
- No tenant-wide delete/reset API; resetting the UI preserves immutable audit. No material pricing: procurement monetary estimates are not fabricated.
- Legacy RC3.1 browser script tests/browser_enterprise_rc3.py is not a valid RC3.4 acceptance test because it asserts the removed five-tab UI. It is retained for history, not counted as PASS.

## Deployment gate (next)

Use GitHub Desktop to update the existing v19-version-b-enterprise-ux-rc31-candidate branch with the changed backend and frontend files. Do not upload only three front-end files; the scenario backend is essential. Manually deploy the existing Render candidate service srv-dbllmt15efls73e4qj60. Reuse Neon branch br-delicate-breeze-bbfceoz1. Only after deployment create new runs A/B/C/D and inspect snapshot source_versions, workflow, decision, outbox, receipt and audit; verify original RC2 branch remains unchanged. No secrets in reports.
