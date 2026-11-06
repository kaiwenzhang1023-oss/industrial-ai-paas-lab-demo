# RC3.4 Windows browser gate compatibility fix

This package is a complete RC3.4 candidate source tree, not a frozen release.

Fixed three browser regression scripts to launch Playwright Chromium without the Linux-only `/usr/bin/chromium` executable path on Windows. Linux CI falls back to `/usr/bin/chromium` if bundled Chromium is unavailable. The existing source SHA256 manifest was recalculated. No business logic, frozen A/RC2, Render, Neon or Docker configuration changed.

On Windows, first install the browser if missing (only once):

```powershell
& 'D:\Anaconda3\python.exe' -m playwright install chromium
```

Then run from the extracted source root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\RUN_FINAL_RELEASE_GATE.ps1' -PythonExe 'D:\Anaconda3\python.exe'
```

The final gate will still be HOLD while independent live tests are outstanding. Preserve `release_evidence/FINAL_RELEASE_GATE_RESULT.json` and `browser_mock.log`.
