# Industrial AI PaaS Lab V1.9 B — RC3.4 Integration Release Candidate

**Important: this is a full source candidate with a reproducible one-shot local gate; it is NOT a Final Release PASS.**

- Source baseline: user-provided RC3.4 full ZIP. No edits to Version A or frozen Version B RC2.
- Changes: tab-scoped, expiring preview-session recovery on reload, validated against `/me`; role/auth negative unit tests; reproducible unified read-only gate; SHA256 provenance audit and release evidence.
- Browser test uses deterministic MOCKED HTTP. Screenshots are NOT live Render browser proof.
- Previous four-scenario PG16 PASS evidence is preserved separately and is not reclassified as new E2E PASS.
- `sessionStorage` contains a bearer token for the lifetime of a browser tab; it is not stored in `localStorage`. This is a deliberate usability/security tradeoff. XSS remains a threat; never put real production credentials into the public preview.
- All writes to PG16, Render deploy, destructive fault injection and new Docker creation are excluded from the one-shot gate. No credentials are included.

## Windows PowerShell 5.1, Python 3.14

Extract ZIP into a NEW candidate directory (do not overwrite RC2 or A), open PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Download\Chatgpt\Industrial AI PaaS Lab\V1.9\V1.9_Version B\Industrial_AI_PaaS_Lab_V19B_RC34\RUN_FINAL_RELEASE_GATE.ps1"
```

Change only the directory path to your actual extracted folder. This checks pytest, syntax, mocked Chromium, source SHA256, Render `/ready` and `/health`, and optionally reads the isolated PG16 branch if `V19B_RC34_ISOLATED_TEST_DATABASE_URL` is set. It will intentionally exit HOLD until the missing cloud/fault/authorization gates are independently evidenced. Requires `pytest`, `playwright`, installed Chromium and `psycopg` only for optional database checks. Never paste credentials into chat or logs.

Evidence outputs to `release_evidence/FINAL_RELEASE_GATE_RESULT.json` and adjacent logs. Return that JSON and sanitized logs, not connection strings.
