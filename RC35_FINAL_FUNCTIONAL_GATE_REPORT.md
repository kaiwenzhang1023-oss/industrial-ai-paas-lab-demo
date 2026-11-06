# RC3.5 — Functional Gate Evidence (2026-11-05)

**Final status: HOLD. This is not a production-ready or approved Render release.**

## Completed now
- Continued from RC3.5 RC6, separate complete source tree.
- Added frozen BOM ancestry validation for every persisted order-material pegging assignment. Detects orphan order/material paths, cyclic BOMs, ambiguous multi-parent graphs and duplicate edges. Does not invent shipment links.
- Retained exact Decimal line-vs-order allocation reconciliation. Any BOM mismatch forces reconciliation status MISMATCH.
- Adjusted business-facing UI terminology, while keeping technical evidence in code and detailed drawers.
- Python test suite: **62 passed** in the current execution environment (Python 3.13). User's Windows Python 3.14 has not been rerun.
- Node syntax and Python compilation PASS.
- Neon isolated PostgreSQL 16.15 branch: **rc35-final-gate-isolated-20261105** (`br-divine-glitter-bb7wf2ve`), READ ONLY check confirmed proposals (14 columns), run inputs, outbox, audit, unique keys/FK, 2 existing runs, 2 internal receipts. No write/integration gate was run against this branch in this turn.
- Chromium automated navigation attempted for file:// and 127.0.0.1. Both **BLOCKED BY ADMINISTRATOR**. No browser PASS.
- Render service discovery confirms existing RC3.4 and Version B candidates; no new service or deployment triggered.

## Blocking defects/gates
1. The existing RC3.4 live PG16 test runner has a hardcoded old endpoint/database allowlist. It CANNOT be run against the new RC3.5 isolated branch without a reviewed safe configuration update and verified credentials. Do not bypass its safety guard.
2. End-to-end PG16 tests (tenant API, approval, Outbox, worker crash/retry, receipt, compensation) unexecuted.
3. G01/G02/G03 only map existing B/C/D scenario overlays; independent datasets and verified golden end-to-end outcomes not available.
4. Complete physical order→supplier/lot/work-order provenance and true MES/WMS/SRM reversal are not implemented; these features must be specified and verified or explicitly scoped as simulations.
5. Browser full-interaction remains blocked in this execution environment.
6. Therefore **no Render RC3.5 deployment attempted**, honoring release order.

## Release rule
Do not mark Final PASS until isolated PG16 end-to-end, browser validation, independent reproducible golden scenario evidence, approved semantics of out-of-scope physical writes, and Render candidate readiness all PASS.
