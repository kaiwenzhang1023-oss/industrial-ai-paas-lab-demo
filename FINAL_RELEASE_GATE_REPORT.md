# RC3.4 Integration Candidate — Final Release Gate (2026-11-05)

## Evidence levels

| Gate | Result | Basis |
|---|---|---|
| RC3.4 four business scenarios in isolated Neon PG16 | PASS (historical, 4/4) | User-supplied database evidence for four run IDs, dated 2026-11-05 |
| Candidate Render deploy RC3.4 | PASS (deployed baseline, not new candidate) | Connected Render service `srv-dbllmt15efls73e4qj60`, deploy `dep-dbm142a3ep3s739ndiq0`, commit `858e75ab756395e780150960540f22a6791eb414` live |
| Frozen RC2 four run IDs absent | PASS (historical read-only check) | Isolated Neon count 4; frozen branch count 0 |
| Local pytest | PASS | Executed on integrated candidate; see `release_evidence/python_pytest.log` |
| Local Chromium UX | PASS (mock HTTP only) | `release_evidence/browser_mock.log` and `evidence/RC33_BUSINESS_FIRST_*.png` |
| JS syntax and Python compile | PASS | `release_evidence/node_js_syntax.log`, `python_compile.log` |
| Source integrity | PASS | `FINAL_SOURCE_SHA256.json`, baseline audit |
| Browser tab refresh restoration | IMPLEMENTED, NOT LIVE VERIFIED | sessionStorage scoped token, `/me` revalidation; unit static contract only |
| New candidate live incognito browser / 5-step / mobile | HOLD | No independent live browser test for changed candidate |
| Cross-tenant 401/403/404 and role matrix | HOLD | Unit auth tests are not PG16 tenant isolation evidence |
| Duplicate/concurrent approval & worker retry | HOLD | No independent live fault/duplicate evidence |
| PG16 fault injection and recovery | HOLD | Not performed, no destructive fault actions authorized |
| A/B same snapshot native reconciliation | HOLD | Existing API does not establish tested parity for all four scenarios |
| What-if pre/post side effects | HOLD | No independent PG16 before/after verification |
| Final Release Gate | **HOLD** | All required enterprise gates have not passed |

## Business semantic constraints

- Scenario C is customer due-date shift +7 days, not MES finite-capacity delay.
- Scenario D is BOM usage doubling and human rejection, not BOM mapping error.
- Worker receipt indicates `INTERNAL_VALIDATION_ONLY`, `external_effect=NONE`. No ERP/MES/SRM external writes.

## Known issues / traceability

1. `enterprise_workbench/site/enterprise-console.js`: tab session recovery is new; it needs real incognito/browser-refresh testing and explicit XSS risk review. No claim of live PASS.
2. `enterprise_workbench/rc2.py`: API-layer tenant scoping and role checks exist, but isolated multi-identity tests are missing. Do not claim PostgreSQL RLS; the inspected tables do not have native RLS enabled.
3. `enterprise_workbench/worker.py`: retry paths exist; live injected transient database failures and lease races remain untested.
4. `enterprise_workbench/rc4.py`: native dynamic reconciliation and what-if are implemented, but new same-snapshot parity and PG16 side-effect checks remain HOLD.
5. `RC34_FILE_SHA256.json` is a legacy historical manifest with missing entries; `FINAL_SOURCE_SHA256.json` is the authoritative candidate manifest. Source baseline differences are recorded in `RC34_BASELINE_CHANGE_AUDIT.json`.
6. Cloud network from this execution container cannot be reliably accessed: `cloud_ready`, `cloud_health` and optional isolated PG16 checks may show HOLD; connector-side Render and Neon reads above are distinct evidence, not substituted for this candidate gate.

## Publication rule

Do not merge to frozen RC2, do not mark Release PASS, and do not deploy the new candidate as a final release until live browser, PG16 fault/recovery, tenant isolation and A/B parity are verified. No new Docker container or Neon branch required.
