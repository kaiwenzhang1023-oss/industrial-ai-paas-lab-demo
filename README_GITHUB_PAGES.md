# RC3 Interactive Simulation Workbench — GitHub Pages

## Scope
Four frozen RC3 scenarios: normal / shortage / delay / bom_change. Browser-only simulation of MRP, MES, SRM, Mapping, Workflow, Agent. Add/edit/delete simulated orders, recalculate, reset, export JSON. Uses original RC3 `public_scenarios.json` as immutable scenario seed. No FastAPI or PostgreSQL required. No Operator key. No actual AI inference or real ERP/MES/SRM writes.

## GitHub Pages deployment
1. Create a **new public GitHub repository** (recommended: `industrial-ai-paas-interactive-demo`) or a separate publishing branch. Upload **only the contents of `github-pages/`** to the repository root. Do not publish the full backend source, credentials, or .env files to the Pages branch.
2. In repository Settings → Pages → Build and deployment, select **Deploy from a branch**, branch `main`, folder `/ (root)`; Save.
3. Visit `https://<your-github-username>.github.io/industrial-ai-paas-interactive-demo/`. Actual URL depends on the repository and account. No site has been deployed by this package.
4. In a private/incognito browser test all four scenarios; add/edit/delete orders, recompute, check each module, export JSON, reset and refresh. No Operator Key prompt should appear.

## Local smoke test
Run `node tests/engine.test.cjs` (Node.js 18+). For browser tests, start an HTTP static server from the `github-pages` directory, e.g. `python -m http.server 8765` then open `http://localhost:8765/` in Chrome. Do not double-click `index.html` because browsers restrict fetch of local JSON via file://.

## Data and safety
All data is simulated and stored under `localStorage` per scenario. Clearing site data removes changes. No multi-user sync, server persistence, authentication, real purchasing, true agent execution or production integration. The mapping failure and supplier delay are **scenario flags**; computation is a teaching approximation, not the verified production MRP algorithm. The original RC3 backend remains in `backend/` and is not changed by this edition. JSON export contains user-entered data: avoid entering confidential information.

## Validation
`node tests/engine.test.cjs` verifies four scenarios, linked modules, shortage math, edits and multiple orders. **Browser E2E and live GitHub Pages deployment have not yet been executed in the user's environment.** Original RC3 Windows 410-pass result applies to the original RC3 gate, not to these new static browser controls.
