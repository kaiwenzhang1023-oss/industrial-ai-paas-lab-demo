# RC3.6 业务功能验收报告（候选）

详见 `RC36_REMEDIATION_MATRIX.md`。

本容器 LOCAL：PASS；117 passed in 0.42s；Node 语法：PASS。

BROWSER：ENVIRONMENT_BLOCKED/HOLD；PG16：HOLD；RENDER：HOLD；A/B 独立同快照实算：HOLD。

## Current gate update — 2026-11-06 (supersedes the earlier 117-pass/Browser-HOLD snapshot)

- Current full Python regression: **134 passed**; Node syntax PASS.
- Windows Chromium/Playwright Browser Mock: **4/4 PASS** (mocked API, not PG16 E2E).
- RC3.6 Neon child branch/schema/runtime permission inspection: PASS via SELECT-only connector inspection.
- Local DSN read-only preflight and real PG16 business DML/Worker/A-B gate: HOLD pending one Windows one-shot execution and explicit authorization.
- Render / browser real E2E: HOLD pending PG16 business PASS.

See `RC36_PG16_PREFLIGHT_REPORT.md` and `release_evidence/rc36/GATE_STATUS.json` for the current status.
