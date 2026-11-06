# RC3.5 RC4 — Enterprise Decision Candidate (development, not release)

## Implemented
- Independent full source tree copied from RC3.5 RC3; RC3.4 and Version A unchanged.
- Additive isolated-PG16 migration `enterprise_workbench/migrations/rc35_001.sql` for tenant-scoped proposal records, input/candidate hashes, idempotency and status.
- New endpoints to save, inspect, cancel, approve/reject, and request compensation review for persisted proposals.
- Proposal creation recomputes the server-side what-if from the persisted canonical snapshot, rejects changed preview hashes, and records audit evidence.
- Approver decision atomically updates existing workflow state, decision row, proposal state, and internal-only Outbox entry. Existing Worker consumes only `VALIDATE_APPROVED_MRP`; **no change is applied to official inventory, schedule, MES, SRM or purchase orders**.
- Compensation endpoint records an auditable **request for review** after internal completion; it does not reverse an executed transaction.
- Human-facing AI comparison headings rewritten to `当前计划 / 调整后的方案 / 方案影响与取舍`; proposal save/review/cancel UI and explicit execution limitations added.
- New tests for role gates, tenant isolation, reviewed-state conflict and compensation scope.

## Local checks
- Python test suite: 49 passed.
- JavaScript syntax: `enterprise-console.js` PASS.
- Real PG16 migration and integration: **HOLD — not run in this environment**.
- Browser E2E, Render/Neon deployment: **HOLD — not run**.

## Still incomplete
- Persisted proposal represents a candidate and an internal validation instruction; no production-grade material allocation / PO / production schedule write adapter exists. Must not describe as actual downstream execution.
- Full batch actions, full multilevel Pegging reconciliation and all three coherent golden scenarios are not yet complete.
- Existing RC3.5 time-bucket calculations require PG16 and browser verification.
- Full error/recovery UX, concurrency/idempotency fault injection and one-shot Windows gate remain to be done.

## Safety and acceptance
- Do not run the additive migration against the frozen RC3.4 production candidate or any shared database.
- Run migration only against an isolated PG16 test database after checking its migration chain and privileges.
- Do not label RC3.5 Final PASS until PG16, browser and deployment gates pass.
