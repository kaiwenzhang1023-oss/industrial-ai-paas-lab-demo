# RC3.6 六项整改逐项完成矩阵与四阶段业务核对

> 状态说明：代码实现≠浏览器验收。本容器自动化浏览器受 URLBlocklist=["*"] 限制；用户 Windows Chromium/Playwright Browser Mock 已实测 4/4 PASS。Neon RC3.6 child branch 的只读结构/权限核验已 PASS，但用户本地 DSN 只读预检及真实 PG16 业务 DML 尚 HOLD；Render 未部署。四张原始问题截图未在本轮工作目录中找到，无法宣称逐像素核对。

| 编号 | 实际源码/函数 | 页面预期效果 | 测试/代码证据 | 结论 |
|---|---|---|---|---|
| R01 双模式切换 | site/app.js: bind; site/enterprise-console.js: activate/deactivate/mode-local | 本地与企业互相进入；企业租户会话保留 | Windows Playwright `test_switch_modes_and_connect` | 代码实现；Browser Mock PASS |
| R02 单位格式 | site/enterprise-console.js: unitOf/quantity; rc35_planning.py | 离散件整数、连续单位精度、普通零值短横线；缺失单位提示 | tests/test_rc36_planning_contract.py; Windows `test_table_numeric_sort_direction_and_zero_units` | 代码实现；Browser Mock 覆盖 PASS |
| R03 净需求/计划供应 | site/enterprise-console.js: runTable/businessPage; rc35_planning.py | 净需求与计划供应量独立列；不同单位不相加 | tests/test_rc36_planning_contract.py; `enterprise_workbench/pg16_validation.py` | 代码实现；离线快照重算 PASS；PG16 真实持久化 HOLD |
| R04 五行供需面板 | site/enterprise-console.js: runTable/visibleRows/action | 双 Tab、行选中、搜索、数值排序升降、分页、钻取、导出 | Windows Playwright table search/sort/page/selection/export + numeric sort/unit tests | 代码实现；Browser Mock PASS |
| R05 会话/异常 | site/enterprise-console.js: request/perform/clearSession | 401 失效、租户校验、刷新恢复、防重提交、错误提示 | tests/test_rc36_session_interactions.py (如存在); browser gate | 部分实现；真实并发与浏览器 HOLD |
| R06 逐行供应解释 | site/enterprise-console.js: verifiedSupplyFor/supplyPolicyDetail; rc35_planning.py | MOQ、批量、计划释放/接收日期、未核验标识 | tests/test_rc36_supply_explanation.py (如存在) | 代码实现；PG16 HOLD |
| S01 需求计算 | site/enterprise-console.js: mrpPage; rc36_lifecycle_contract.py | 快照、毛需求/净需求与来源日期 | tests/test_rc36_lifecycle_extended.py | 代码审计；PG16 HOLD |
| S02 供应建议 | site/enterprise-console.js: supplyPolicyDetail; rc35_planning.py | 计划供应不等于实际采购/生产承诺 | tests/test_rc36_lifecycle_extended.py | 代码审计；PG16 HOLD |
| S03 人工审批 | site/enterprise-console.js: approvalPage/action; rc36_lifecycle_contract.py | 待审核→批准入队/驳回终止，审计原因 | tests/test_rc36_lifecycle_extended.py; Windows `test_four_stage_approval_receipt_and_reload` | 页面 Browser Mock PASS；PG16 持久化 HOLD |
| S04 内部执行/回执 | site/enterprise-console.js: executionPage/receiptPage/auditPage | Outbox 状态、Worker 内部验证、持久化回执及审计 | tests/test_rc36_lifecycle_extended.py; Windows `test_four_stage_approval_receipt_and_reload` | 页面 Browser Mock PASS；PG16 Worker/回执持久化 HOLD |
| AB 同快照对账 | enterprise_workbench/reconciliation.py | 来源指纹不同拒绝对账通过 | tests/test_rc36_reconciliation_provenance.py | 契约实现；独立 A/B 实算 HOLD |

## 门禁

- LOCAL：**PASS**；当前工作树完整回归 134 passed（本容器 Python 3.13.5），Node 语法检查 PASS；Windows PG16 一次性脚本将用 Python 3.14.x 再执行。
- BROWSER_MOCK：**PASS 4/4**；用户 Windows Chromium/Playwright 实测 4 项全部通过（6.07s，mock API，不是 PG16 E2E）。容器 URLBlocklist 诊断只描述容器环境，不再覆盖 Windows 浏览器实测结果。
- PG16 branch metadata/schema：**PASS（只读 connector 检查）**；本地 DSN read-only preflight：**HOLD**；真实 PG16 业务门禁：**HOLD**，尚未执行 DML/Worker fault injection。
- RENDER：**HOLD**，未部署。
- A/B 独立引擎同快照算法预演：A/B/C/D 数量与 Pegging MATCH；Neon PG16 真实对账：**HOLD**。

## 本轮页面修复

- 表格数值字段改为数值排序，重复点击切换升降序，避免字符串排序 `1,10,2`。
- 排序时清除旧行选中，防止行语义变化后误钻取。
- 本地模式按钮复用已有真实模式切换入口，避免双重触发。
- 剪贴板不支持时明确报错，不再假报复制成功。
- 步骤完成状态不把 DEAD 失败命令当成执行成功；DONE 需有回执。
- 企业就绪检查必须同时满足 status=ready 和 database=postgresql。

## 页面业务示例（来自测试模拟，不是 PG16 实测）

测试数据含 M-00～M-18 共 19 行，需求日期 2026-11-20，首行毛需求 1、净需求 1、计划供应 2；页面按 12 行分页，第二页 7 行。该数据仅用于浏览器控件测试，不能作为真实企业业务结果。

## 剩余阻塞与冻结条件

真实浏览器端到端、Windows Chrome 执行、隔离 PG16 持久化/并发、Render 部署、独立 A/B 同快照实算及四张原始截图视觉复核均未通过，因此本包是 **Full Source 候选**，不是冻结正式版。

## Windows 浏览器门禁环境修复（2026-11-06）

- 用户首次执行 `RUN_RC36_WINDOWS_BROWSER_ONE_SHOT.ps1`：**ENVIRONMENT_DEPENDENCY_MISSING / HOLD**；日志证实误选 Windows Python 3.10.4，且该解释器未安装 `playwright`，pytest 在收集阶段失败，未执行浏览器测试。此错误不能视为 Workbench 业务 FAIL，也不能视为浏览器 PASS。
- 已更新脚本：严格选择 Python 3.14（支持 `-PythonExe` 显式路径）；建立独立 `.rc36-browser-venv`；安装 pytest/Playwright/Chromium；执行浏览器测试并写入 `release_evidence/rc36/WINDOWS_BROWSER.log` 和 `BROWSER_STATUS.txt`。未禁用安全策略。
- 修复后的 Windows Chrome/Playwright 实测：**HOLD（等待用户在 Windows 执行）**。若网络无法下载依赖或浏览器被管理策略拦截，保持 HOLD，保留日志。


## PG16 独立集成门禁阶段（2026-11-06）

### 实际分支与权限预检查

- RC3.6 Neon child branch `br-green-glade-bbnahfli` / `rc36-pg16-isolated-20261106` 状态 `ready`，parent 为 RC3.5 隔离测试分支 `br-divine-glitter-bb7wf2ve`；独立 endpoint `ep-holy-star-bbv8lyg7` 当前 `active`，数据库 PG 16.15。
- SELECT-only 结构核验：29 张可见业务表，PG16 gate 所需 20/20 表和 20/20 字段组齐备；2 个关键索引和 proposal 状态约束存在；migration ledger 0 张。
- 种子数据：2 个订单、9 个物料、1 个释放 BOM 版本、8 条 BOM、5 条确认在途、9 条库存；9/9 物料有 UOM（PCS）。当前 RC3.6 gate tenant/run 行均为 0。
- 最小权限角色 `v19b_app_runtime` 非 superuser、无 CREATEDB/CREATEROLE，36 项所需表权限、4 项 schema USAGE 和 audit sequence USAGE 全部通过。连接 guard 已拒绝 owner/superuser 角色，只允许该 runtime role、精确 RC3.6 host/database 和 SSL。
- Connector 本轮只执行 SELECT；没有 DDL、DML、迁移、故障注入或 RC3.5 父分支写入。

### 新增业务证据验证

- `enterprise_workbench/pg16_validation.py`：从 run snapshot 独立重算 BOM gross、库存/确认在途抵扣、net、MOQ/lot planned、closing；检查 Pegging stock/receipt/planned 来源池不超额。
- `g4/core.py`：A/B 动态同快照对账增加订单级 Pegging parity；A 引擎丢失订单归属时返回 HOLD，不猜测。
- `tests/rc36_isolated_pg16_gate.py`：增加场景绑定 snapshot fence、持久化事实重算、Pegging 来源上限、A/B order-level Pegging、decision→outbox→receipt→worker audit 时间顺序。
- 本地 seed replay A/B/C/D：snapshot recompute MATCH、supply caps MATCH、native A/B 数量 MATCH、order-level Pegging MATCH；此为离线预演，不是 PG16 真实业务 PASS。

### 门禁状态与一次性执行

| 门禁 | 状态 |
|---|---|
| LOCAL | PASS：134 passed；Node syntax PASS |
| BROWSER_MOCK | PASS：Windows 4/4（用户实测） |
| PG16 branch/schema metadata | PASS：只读 connector 检查 |
| PG16 local DSN read-only preflight | HOLD：等待 Windows 隐藏 DSN 输入 |
| PG16 real business DML/Worker/A-B | HOLD：需 read-only PASS 后显式授权 |
| RENDER / Browser real E2E | HOLD：等待 PG16 真实业务 PASS |

唯一执行脚本：`RUN_RC36_PG16_ONE_SHOT.ps1`；依赖清单：`requirements-rc36-pg16-gate.txt`。脚本默认通过 `py.exe -3.14` 定位 Python 3.14，执行完整本地回归与只读 PG16 预检。只有输入完整授权短语 `RUN_RC36_ISOLATED_PG16_WRITES_AND_FAULT_TESTS` 才会在 RC3.6 child branch 插入 `rc36gate-*` 业务测试数据并执行一次应用层 Worker fault/retry；脚本不运行迁移/DDL，不改 mock ERP/WMS 源表，不触碰 RC3.5。

详细证据见 `RC36_PG16_PREFLIGHT_REPORT.md` 和 `release_evidence/rc36/PG16_BRANCH_READONLY_INSPECTION.json`。

### 2026-11-06 Windows PG16 一键脚本启动修复（本地未复测）

- 用户 Windows 回传：`GATE_STOPPED: File "<string>", line 1`；LOCAL=HOLD、PG16_READONLY=HOLD_NOT_RUN、PG16_BUSINESS=HOLD_NOT_RUN。定位在 `RUN_RC36_PG16_ONE_SHOT.ps1` 内 Python `-c` 版本探针引号，属于 Windows PowerShell 5.1 参数转义问题；未进入数据库阶段，非业务 FAIL。
- 修复 `Resolve-Python314` 的 fallback 探针及主解释器/venv 的版本探针，统一改为不包含双引号的 Python 单行表达式（`sys.version_info.major*100+sys.version_info.minor`、`print(...,sep=chr(46))`）。这消除了此前 `print(".".join(...))` 在 PowerShell 5.1 下双引号丢失导致的语法错误。
- 修复后的脚本在 Linux 侧完成文本/命令静态核对；**Windows 上的修复验证尚未执行，LOCAL 新门禁仍 HOLD**。保留此前 134 passed（历史本地证据）和 Windows Browser Mock 4/4 PASS（用户实测）；PG16 DSN、真实业务、Render 均为 HOLD。
- 不涉及迁移、数据库写入、RC3.5 变更；仅更新当前 RC3.6 工作树中的同名脚本和整改矩阵。
