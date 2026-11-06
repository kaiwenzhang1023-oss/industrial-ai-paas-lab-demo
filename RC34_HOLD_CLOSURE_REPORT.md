# RC3.4 HOLD closure candidate — evidence status

- Immutable: Version A V1.9, Version B RC2 and existing RC3.4 deployment; no database writes.
- Local pytest: 25 PASS (20 prior tests + 5 deterministic A/B reconciliation contract tests).
- Live read-only browser probe attempted in this sandbox: HOLD (network/browser restrictions; see release_evidence/live_readonly/RESULT.json). No real screenshot generated.
- Render connector: RC3.4 deployment dep-dbm142a3ep3s739ndiq0 remains live, commit 858e75ab756395e780150960540f22a6791eb414.
- Live browser script performs read-only desktop/mobile public-page smoke checks and saves actual screenshots only when successful; not a complete login/workflow acceptance.
- Existing full Final Release Gate remains HOLD. Tenant auth, idempotency, Worker fault recovery, A/B dynamic same-snapshot, What-if no-side-effects and isolated PG16 remain unverified in this iteration.
- This ZIP is an intermediate candidate, NOT a frozen final release. Do not deploy it as frozen release.
