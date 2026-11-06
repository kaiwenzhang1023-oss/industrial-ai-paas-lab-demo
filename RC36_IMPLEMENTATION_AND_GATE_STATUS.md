# RC3.6 源码实施与门禁状态（开发检查点，非最终整版验收）

基线：RC3.5 Parser Fix 完整源码 + 前轮 RC3.6 单位及需求日期契约；保留既有数据库迁移及后端兼容字段。

## 六项整改

| 需求 | 本轮源码证据 | 状态 |
|---|---|---|
| P0-01 双模式 | enterprise-console.js 企业返回本地入口；原 app.js 双模式入口；状态不清空 | PARTIAL：浏览器往返及刷新未实测 |
| P0-02 单位 | unitOf / quantity；缺单位警告、整数异常提示、零值/缺失区分 | PARTIAL：单位主数据全覆盖及小数精度规则需验证 |
| P0-03 净需求 | UI 净需求；后端兼容别名 net_requirement，保留 legacy semantics | PARTIAL：全页面/导出术语复查未闭环 |
| P0-04 五行面板 | Tab、搜索、行选中、明细、排序、分页、导出、图例；无工单不伪造 | PARTIAL：真实浏览器交互未实测 |
| P1-05 全控件 | 表格键盘行选择、禁用按钮、筛选及导出 | HOLD：全控件真实浏览器门禁未运行 |
| P1-06 关联契约 | 来源需求日期、单位、订单净需求不可用说明、快照导出、内部/外部状态分离 | PARTIAL：完整 PG16 关联及审批/Worker 故障门禁未运行 |

## 四阶段语义

1. 需求计算：保留毛需求、净需求、单位及来源需求日期；订单级净需求无可信字段，不伪造。
2. 供应建议：区分净需求与计划供应量；未确认计划供应分配不是完整供应量。MOQ/批量行级解释尚待增强。
3. 人工审批：既有后端审批与幂等逻辑保留；本轮未宣称新的 PG16 审批测试。
4. 内部执行：UI 明确 Worker 内部执行与外部履约未验证；不宣称外部生产或采购执行。

## 实测

- Python 本地环境 `python -m pytest -q tests`: **86 passed**（保留既有 81 项并增加 5 项 UI 源码契约测试）。
- Node `--check enterprise-console.js`: PASS。
- Python 3.14.6 Windows 门禁：HOLD（本环境并非用户 Windows）。
- 隔离 PostgreSQL 16、Neon、A/B 真实数据对账：HOLD（未执行）。
- 真实浏览器 Workbench E2E、Render：HOLD（未执行）。
- **整版 RC3.6：HOLD；本包为开发检查点，不能作为最终冻结/部署验收包。**

注意：静态 UI 契约测试不能替代真实浏览器行为测试。不得将历史 RC3.5 PG16 PASS 当作 RC3.6 PG16 PASS。

## 2026-11-06 同工作树增量（未冻结）

- 物料需求表选中行新增 `verifiedSupplyFor` / `supplyPolicyDetail`，从 `/planning/time-buckets/{run}` 返回的 `supply_explanations` 精确匹配物料与需求日期；展示净需求、建议量、差额、MOQ、采购/生产批量、需求/接收/释放日及提前期。
- 仅在 `explain_supply` 返回 `VERIFIED` 时说明 MOQ 和批量取整生效；无证据、规则不匹配、日期不匹配均不得推断；外部履约仍未验证。
- 新增 `tests/test_rc36_supply_explanation_ui.py` 六项测试；全量 `python -m pytest -q tests` 为 **92 passed**，`node --check` PASS。
- 该结果仅为本地静态/单元回归。完整浏览器控件、刷新恢复、PG16 故障注入、A/B 同快照实际数据对账及 Render 门禁均未完成，整版保持 HOLD。
- 不产生阶段性 ZIP；不改 RC3.5 冻结版本。

## 2026-11-06 同工作树继续开发：会话及表格交互防护

- enterprise-console.js：新增 sessionEpoch 和请求发起时的 tenant/epoch 捕获；旧会话返回数据在处理前拒绝，401 清除会话；刷新恢复要求有效的 expiresAt 数值及服务端租户校验。
- 行列表：排序字段白名单、分页上下界、搜索/分页行选中清理、可见行校验；忙碌期间不重复派发按钮动作。
- tests/test_rc36_session_interaction_guards.py：新增 5 项静态安全契约检查。
- 本地 `PYTHONPATH=.:backend python -m pytest -q tests`：97 passed；`node --check enterprise_workbench/site/enterprise-console.js`：PASS。
- 仍未完成真实浏览器 E2E、A/B 同快照数据对账、PG16 隔离门禁和 Render 验收；RC3.6 Final：HOLD。未生成 ZIP。

## Current PG16 integration-preparation status (2026-11-06; supersedes earlier checkpoint counts)

- Current worktree full Python regression: **134 passed** (container Python 3.13.5); Node syntax checks PASS; current source manifest is verified file-by-file.
- Windows Chromium/Playwright Browser Mock: **4/4 PASS** (user-provided result; mocked API, not PG16 E2E).
- Neon RC3.6 child branch metadata/schema/seed/runtime-role permissions: **PASS, SELECT-only connector inspection**. The branch is `rc36-pg16-isolated-20261106`, child of the RC3.5 isolated test branch; no branch writes were made.
- Windows DSN read-only preflight: **HOLD**; actual user's local runtime-role connection has not yet been tested.
- Real PG16 business DML/Worker/A-B gate: **HOLD**; fail-closed execution without DSN was verified and wrote no database data. The one-shot script requires explicit acknowledgement before test writes/fault injection.
- Render and browser real E2E: **HOLD**, correctly deferred until PG16 business gate PASS.
- Current source-of-truth: `RC36_REMEDIATION_MATRIX.md`, `RC36_PG16_PREFLIGHT_REPORT.md`, `docs/RC36_PG16_MIGRATION_REVIEW.md`, and `release_evidence/rc36/GATE_STATUS.json`.
