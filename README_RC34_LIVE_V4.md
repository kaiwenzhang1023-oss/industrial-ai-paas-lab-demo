# RC3.4 Live Business Browser V4 — self-contained overlay

## Why V4 exists

`RESULT(4).json` recorded 13 passing browser checks, including persisted Worker DONE, the internal-only receipt, and rendered audit timeline. The V3 optional `/what-if` request returned HTTP 422 because the gate sent the integer `quantity: 80` to `WhatIfRequest.quantity: str | None`. The hardcoded material target was also unsafe. On failure the screenshot hook ran *after* the Playwright context closed, so it produced `Event loop is closed` instead of `FAIL_AT_STEP.png`.

## What V4 does

- Uses only the isolated Render RC3.4 candidate, creating a new guest run in a new tenant.
- The same MRP → refresh → approve → Outbox → internal Worker DONE → receipt → audit flow.
- Reads the persisted canonical snapshot for its material ID and computes a valid decimal quantity (as a **string**), then calls `/what-if` with explicit `Content-Type: application/json`.
- Checks What-if API side-effect contract and rereads the same persisted MRP snapshot and business overview to check unchanged state. This is **not** a substitute for the 12-table direct PG16 evidence, already provided in the previous PG16 gate.
- Runs a *real native JS Version A vs persisted Version B* reconciliation after the no-side-effect proof, and tests cross-tenant 404 and no-auth 401.
- Captures screenshot **before** closing the browser, records every stage immediately and includes the safe HTTP 422 validation detail if one recurs.
- Does not expose bearer tokens, passwords, or connection URLs in reports.
- Keeps the 106-file release baseline byte-for-byte unchanged, including `FINAL_SOURCE_SHA256.json`; the new V4 gate is an additive audit script with its **own** hash record. Thus prior 137/137 PG16 certificate `source_manifest_sha256=cbaa374b...` remains tied to the same released product source. V4 is not part of the old 106-file manifest and must be verified via `RC34_LIVE_V4_OVERLAY_SHA256.json`.

## Run once on Windows PowerShell

Extract this full ZIP to a new folder, enter its `Industrial_AI_PaaS_Lab_V19B_RC34` directory, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC34_LIVE_BUSINESS_GATE_V4.ps1" -PythonExe "D:\Anaconda3\python.exe"
```

- Expected: `LIVE_BUSINESS=PASS` and `LIVE_BUSINESS_EXIT=0` (only if all live checks pass).
- Evidence: `release_evidence\live_business\RESULT.json`, `release_evidence\FINAL_RELEASE_GATE_V4_RESULT.json`, `01_mrp.png`, `02_approval.png`, `03_receipt.png`, `04_audit.png`.
- If FAIL: submit `RESULT.json` and `FAIL_AT_STEP.png`; the latter is best-effort if the browser cannot start.
- **Do not re-run** if FAIL without inspecting the evidence. The script creates a new isolated test MRP on each invocation.
- Does not re-run 137 PG16 checks, does not deploy GitHub/Render, does not require DB credentials or Docker.

**Final Release Gate is still HOLD until actual V4 cloud result and a separately reviewed frozen-RC2 read-only branch comparison are available.** Never convert test harness syntax PASS into cloud workflow PASS.

The same one-shot command automatically runs the additive `RUN_RC34_FINAL_RELEASE_GATE_V4.py` consolidation. Its final status is intentionally `HOLD` until the post-gate Render commit is independently rechecked; evidence completeness is reported separately. No second local command is required.
