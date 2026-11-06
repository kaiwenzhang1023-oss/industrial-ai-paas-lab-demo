RC3.4 Live Business Gate V3 — Worker state machine fix (2026-11-05)

Previous RESULT(3).json: MRP, refresh and approval passed; test incorrectly waited for dispatch to re-enable after Worker execution. DONE correctly disables dispatch.

Fix: wait on real authenticated backend overview.command.status==DONE; refresh receipt; audit selector updated to .vbc-business-timeline; screenshot errors reported separately. No changes to application, GitHub, Render, or frozen RC2.

Run in extracted full source root:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC34_LIVE_BUSINESS_GATE.ps1" -PythonExe "D:\Anaconda3\python.exe"

The gate creates a NEW guest MRP because a previous process's tab-scoped session token is not reusable. If FAIL, return release_evidence\live_business\RESULT.json and any screenshots; do not rerun blindly.
