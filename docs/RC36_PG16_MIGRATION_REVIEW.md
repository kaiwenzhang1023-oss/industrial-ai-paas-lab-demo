# RC3.6 PostgreSQL 16 migration and schema review

Review date: 2026-11-06 (UTC)

## Target isolation

- Neon project: `industrial-ai-paas-v19-version-b-preview` (`super-glade-55757112`)
- New child branch: `rc36-pg16-isolated-20261106` (`br-green-glade-bbnahfli`)
- Parent: existing RC3.5 isolated test branch `rc35-final-gate-isolated-20261105` (`br-divine-glitter-bb7wf2ve`)
- Dedicated endpoint: `ep-holy-star-bbv8lyg7`
- Database: `industrial_v19b_preview`
- PostgreSQL observed through read-only Neon query: `server_version_num=160015` (16.15)

The RC3.6 branch is a new branch. No SQL migration, DML, fault injection, or source-table update was run during setup. The parent RC3.5 isolated branch and frozen RC3.5/RC3.4/V1.8 services were not modified.

## Migration files found in the RC3.6 source tree

| File | SHA-256 |
|---|---|
| `enterprise_workbench/migrations/rc2_001.sql` | `13d5cefff1d8d300798da8f4ecac4425d8c95cd51f8babc341eb2bcda2cdc74f` |
| `enterprise_workbench/migrations/rc2_002.sql` | `1a60d04db7d070d94cf23326406a3650854bba018668983ce82c064a39814dc2` |
| `enterprise_workbench/migrations/rc3_001.sql` | `9af282a5d1ae1a4861f03372bcbfa1851f41948c74e3b654182d69832d0caff2` |
| `enterprise_workbench/migrations/rc35_001.sql` | `70f21304a7c7a7aebd78cc576128a9a44b2f6f5dd8c769388de561ffd41b198b` |
| `enterprise_workbench/migrations/rc35_002.sql` | `08177b51104dff8e6d38ad320f15004b13feeaa3d893e5621e6165c2f359a77d` |
| `database/003_v03.sql` | `ecd96b09c3af753407559b6cdf0a5b5986094a857377fa8e02738a017dbe5146` |
| `database/004_snapshot_fence.sql` | `ee4c560928136fedeb68c6ae026ac167157fa05e8da49c9715b80ddd231afa83` |
| `database/schema.sql` | `b84ebd32805af35222c17b2a518a55d6739f93daec24a72b10fa46a4821ba0fd` |

## Observed database structure and seed evidence (read-only)

The new branch was inspected with SELECT-only queries. The following source objects and RC2/RC3/RC3.5 objects exist:

- `mock_erp.sales_orders`, `materials`, `bom_versions`, `bom_items`, `supply_orders`
- `mock_wms.inventory_balances`
- `platform.requirement_runs`, `material_requirements`, `requirement_pegs`, `run_snapshot_fences`
- `version_b_rc2.run_tenants`, `run_inputs`, `workflow_states`, `decisions`, `outbox`, `execution_receipts`, `audit`, `reconciliation`, `proposals`, `mcp_call_audit`

Observed source seed data includes 2 confirmed sales orders, a released `EM-100/V1` BOM with 8 BOM lines, 9 material masters, 9 inventory balances and 5 confirmed supply-order rows. Material master UOM values observed were `PCS`.

The branch has existing completed MRP run evidence inherited from its RC3.5 isolated parent. Those historical rows are not counted as RC3.6 test evidence. The RC3.6 gate creates fresh `rc36gate-*` tenants and new run IDs.

## RC3.6 schema decision: no new DDL migration is currently required

The observed source schema already has `mock_erp.materials.uom`. The RC3.6 code change binds this value into the immutable `Item` snapshot and the `version_b_rc2.run_inputs.payload` JSONB record; the persisted run fingerprint therefore includes UOM. The material-requirement fact table remains numeric and its unit is resolved from that run's immutable JSON snapshot, avoiding an unsafe cross-run join to mutable master data.

The existing `platform.material_requirements` table does not store `release_date`. RC3.6 therefore reports release date as `need_date - lead_days` from the immutable run snapshot and explicitly labels its provenance `DERIVED_FROM_FROZEN_SNAPSHOT`; it does not claim the derived date is a separately persisted database column.

No `rc36_*.sql` migration is added or executed. This is deliberate: the current gate uses existing JSONB and source-master columns, and does not require DDL. If read-only preflight finds a missing required table/column or constraint, it stops before any write and records HOLD/FAIL; it does not auto-migrate.

## Migration provenance limitation

The read-only inspection found no migration-ledger/schema-version table. Therefore the database's migration history cannot be proven from a ledger. The PG16 preflight checks the actual required tables, columns, indexes and proposal state constraint structurally. The final report must retain `STRUCTURE_VERIFIED_NO_LEDGER` rather than claiming a ledger-verified migration sequence.

## Safety boundary

`RUN_RC36_PG16_ONE_SHOT.ps1`:

1. runs LOCAL tests and Node syntax checks;
2. asks for a hidden connection string and accepts only the exact RC3.6 endpoint host and database;
3. runs a transaction-read-only preflight;
4. does not execute migrations;
5. requires the explicit phrase `RUN_RC36_ISOLATED_PG16_WRITES_AND_FAULT_TESTS` before inserting only RC3.6 unique tenant/run/workflow test records and performing one application-level worker failure/retry test;
6. compares source ERP/WMS table fingerprints before and after.

No Neon endpoint outside the exact RC3.6 allowlist is accepted. The pooled endpoint is rejected.

## Live branch metadata and least-privilege verification (2026-11-06)

A second read-only inspection confirmed the branch endpoint is active, the branch state is `ready`, and the branch has zero written data bytes at the observation. `information_schema` reports 29 visible business tables; all 20 tables required by the PG16 gate and all 20 required column groups are present. The proposal status constraint, single-terminal-decision index, and Outbox lease polling index are present. No migration-ledger table exists.

The gate role is `v19b_app_runtime`, not `v19b_preview_owner` and never `cloud_admin`. Role metadata confirms it is not a superuser and cannot create databases or roles. Its 22 required source-read / workflow-write table privileges are present. The connector inspection itself used `v19b_preview_owner` for SELECT-only metadata queries; this does not authorize that owner role for the user's gate DSN. The one-shot PowerShell gate rejects any DSN whose username is not exactly `v19b_app_runtime` and the read-only preflight verifies the role again on the user's own DSN.

At this observation, `version_b_rc2.run_tenants` contained zero `rc36gate-*` tenants and `platform.requirement_runs` contained zero runs belonging to such tenants. No RC3.6 business gate had run.

## Enhanced RC3.6 PG16 evidence validators

- `enterprise_workbench/pg16_validation.py` independently recomputes persisted daily gross/net/planned/closing facts from the immutable snapshot, including BOM explosion, inventory, confirmed dated receipts, safety stock, MOQ, lot multiple and MAKE planned-lot explosion.
- The same module verifies that persisted order-level pegging does not exceed the chronological opening-stock, confirmed-receipt and planned-supply pools.
- `g4.core.dynamic_comparison` now adds order-level Pegging comparison between the frozen native A engine's source origins and persisted PG16 pegs. If Version A collapses multiple order origins to `MULTI_ORDER`, the result is HOLD rather than an invented order-level match.
- The PG16 gate now checks scenario-bound snapshot fence, independent snapshot-to-fact recompute, supply source caps, order-level Pegging parity and proposal/decision/Outbox/receipt/Worker audit timestamp order.

The local seed replay for scenarios A/B/C/D returned snapshot recompute MATCH, supply caps MATCH, numeric A/B MATCH and order-level Pegging MATCH in each scenario. This is a local algorithm replay using the currently observed seed rows; it is not a Neon PG16 business-gate PASS.

## Reproducible offline seed replay (not a PG16 business PASS)

The SELECT-captured branch seed is stored in `release_evidence/rc36/PG16_BRANCH_SEED_SNAPSHOT.json`; `gates/rc36_offline_seed_replay.py` replays scenarios A/B/C/D without a database connection. All four scenarios currently report snapshot recompute MATCH, supply source caps MATCH, native A/B numeric MATCH, and order-level Pegging MATCH. Output: `release_evidence/rc36/PG16_OFFLINE_SEED_REPLAY.json`, explicitly `PASS_OFFLINE_ONLY`. The live PG16 gate still has to reload the database through the user-supplied RC3.6 DSN and verify persisted rows.
