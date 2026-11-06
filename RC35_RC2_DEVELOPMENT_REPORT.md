# RC3.5 RC2 — Integrated Development Candidate

Status: **DEVELOPMENT CANDIDATE / CLOUD & PG16 GATES HOLD**.

Baseline: RC3.5 RC1, copied into a separate RC2 full source tree. RC3.4 and Version A were not modified.

## This batch
- Added tenant-authorized PostgreSQL audit-history API: `GET /api/v1/version-b/enterprise/audit/history`.
- Filters: `run_id`, `action`, `actor`, `before_id`; server-side cursor pagination, maximum 100 rows/page.
- Tenant scope always taken from verified identity, never a client-controlled tenant parameter.
- Explicit cross-tenant run existence check returns 404; unauthorized role returns 403.
- Added audit center in enterprise MRP workspace with live search, paging, empty/error states.
- Linked existing `工作流与审计` entry to the enterprise audit context.
- Retained the existing MRP enterprise exception matrix, receipt highlights, local/enterprise mode separation.
- Added focused audit API contract tests and updated the mode-entry contract test for the new event handler.

## Evidence
- Local pytest: 37 passed.
- JavaScript syntax: app.js / enterprise-console.js / engine.js passed.
- Python bytecode compilation: pending below.
- No PostgreSQL database was accessed; no Render/GitHub deployment performed.
- No claim of real database or browser end-to-end PASS.

## Remaining high-priority work
- Audit real PG16 integration, permission boundary and browser E2E.
- Time-Bucket stock flow and order-impact pegging verified against backend.
- AI As-Is/To-Be/Trade-off proposal lifecycle, bulk decision, rollback/compensation.
- Three golden scenarios, complete UX/browser regression, unified release gate.

Worker remains INTERNAL_VALIDATION_ONLY; no actual MES/SRM commands.
