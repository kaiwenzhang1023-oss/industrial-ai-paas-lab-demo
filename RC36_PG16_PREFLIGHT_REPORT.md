# RC3.6 独立 PG16 集成门禁预检查报告

观察时间：2026-11-06 09:33（UTC+08:00）  
工作树：当前 `/mnt/data/rc36_active`；不重建 RC3.5/RC3.6 基线。

## 1. 独立 Neon 分支身份

**只读检查 PASS**

| 项目 | 已核验值 |
|---|---|
| Neon 项目 | `industrial-ai-paas-v19-version-b-preview` |
| Project ID | `super-glade-55757112` |
| RC3.6 分支 | `rc36-pg16-isolated-20261106` |
| Branch ID | `br-green-glade-bbnahfli` |
| 分支状态 | `ready` |
| 父分支 | `rc35-final-gate-isolated-20261105` (`br-divine-glitter-bb7wf2ve`) |
| 独立 endpoint | `ep-holy-star-bbv8lyg7` |
| endpoint 状态 | `active` |
| 数据库 | `industrial_v19b_preview` |
| PostgreSQL | `160015`（16.15） |

此 RC3.6 分支是 RC3.5 **隔离测试分支**的子分支，不是 RC3.5 正式/默认数据库。Neon 分支元数据当前 `written_data_bytes=0`；RC3.6 测试 tenant/run 计数均为 0。当前未对父分支或其他历史分支执行写入。

## 2. Schema、迁移和种子数据

| 检查 | 实测结果 |
|---|---:|
| 可见业务 schema 表 | 29 |
| PG16 门禁必需表 | 20/20 存在 |
| 必需字段组 | 20/20 无缺失 |
| `rc2_single_terminal_decision` | 存在 |
| `rc2_outbox_lease_poll` | 存在 |
| Proposal 状态约束 | 存在，包含补偿状态 |
| migration/schema-version ledger | 0 张 |
| `mock_erp.sales_orders` | 2 行 |
| `mock_erp.materials` | 9 行 |
| `mock_erp.bom_versions` | 1 行 |
| `mock_erp.bom_items` | 8 行 |
| `mock_erp.supply_orders` | 5 行 |
| `mock_wms.inventory_balances` | 9 行 |
| 物料 UOM | 9/9 有值，当前均为 `PCS` |

源码迁移清单为 8 个 SQL 文件：

- `enterprise_workbench/migrations/rc2_001.sql`
- `enterprise_workbench/migrations/rc2_002.sql`
- `enterprise_workbench/migrations/rc3_001.sql`
- `enterprise_workbench/migrations/rc35_001.sql`
- `enterprise_workbench/migrations/rc35_002.sql`
- `database/schema.sql`
- `database/003_v03.sql`
- `database/004_snapshot_fence.sql`

8 个文件 SHA-256 与 `docs/RC36_PG16_MIGRATION_REVIEW.md` 中的清单一致。没有 `rc36_*.sql` 迁移；当前四阶段 PG16 gate 使用继承 schema 中的 MRP facts、snapshot JSONB、workflow、decision、outbox、receipt、audit 和 reconciliation，不需要新增 DDL。由于数据库没有 migration ledger，报告只允许使用 `STRUCTURE_VERIFIED_NO_LEDGER`，不声称迁移历史已由 ledger 证明。

**本阶段不会执行任何迁移或 DDL。** 如果实际本地 DSN 预检查发现缺表、缺字段、缺索引或缺权限，门禁将停止并 HOLD/FAIL，不会自动修复数据库结构。

## 3. 数据库连接角色与最小权限

已只读核对 `v19b_app_runtime`：

- 角色存在且可登录；不是 superuser；`CREATEDB=false`、`CREATEROLE=false`。
- 对 PG16 gate 所需的源表 SELECT、MRP 事实写入、run snapshot、workflow、decision、outbox、receipt、audit、reconciliation、proposal 等 **36 项表权限、4 项 schema USAGE 和 audit sequence USAGE 全部具备**。
- Neon connector 当前查询身份是 `v19b_preview_owner`，不是业务 gate 应使用的 runtime role。故本地脚本现已强制 DSN 用户名为 `v19b_app_runtime`，拒绝 owner/superuser 连接。

本地脚本还会在用户 DSN 会话中验证 `current_user`、`transaction_read_only=on`、PG16 版本、数据库名、表结构、种子数据和权限。Connector 的只读 SELECT 检查不能替代这个本地 DSN 检查。

## 4. RC3.6 本地门禁和新增证据逻辑

当前工作树完整 Python 回归：**134 passed**（容器 Python 3.13.5）；Node 三个关键文件语法检查 PASS；当前源码 manifest 覆盖 187 个代码/配置文件，SHA-256 `eea03501a804549939bc21e7b31849a142d45ee13bc8bdc17a1f644a6f172d19`，逐文件完整性校验无缺失/不匹配。Windows 一次性 PG16 脚本会在用户 Python 3.14.x 环境重新执行完整本地回归，Browser Mock 不会重复运行。

本轮补齐了 PG16 业务证据验证：

1. `enterprise_workbench/pg16_validation.py` 从不可变 run snapshot 独立重算 BOM 展开、库存/在途抵扣、净需求、MOQ/批量、计划供应及结余，并与 PG16 持久化事实逐行比对。
2. 同一模块检查 order-level pegging 的 stock / confirmed receipt / planned supply 分配是否超过按日期可用池。
3. `g4/core.py` 的动态 A/B 对账增加订单级 Pegging 对账；Version A 无法保留订单归属时返回 HOLD，不会把 `MULTI_ORDER` 猜成订单级 PASS。
4. PG16 gate 对每个 A/B/C/D run 检查快照时间/场景、MRP 重算、Pegging 来源上限、BOM lineage、逐行 MOQ/提前期解释。
5. Proposal → Approval → Outbox → Receipt → Worker Audit 增加数据库时间顺序检查。

以上新增逻辑已用本地快照样例 A/B/C/D 做离线预演：每个场景的 snapshot recompute、supply caps、native A/B 数量与 order-level Pegging 均 MATCH。**这些是离线算法预演，不是 Neon PG16 真实业务 PASS。**

## 5. 四类门禁当前状态

| 门禁 | 当前状态 | 证据/下一步 |
|---|---|---|
| LOCAL | PASS | 134 passed；Node syntax PASS。Windows 一次性脚本将用 Python 3.14.x 再跑 |
| BROWSER_MOCK | PASS | 用户 Windows Playwright 实测 4/4；本阶段不重跑 |
| PG16 branch metadata/schema | PASS（只读 connector 检查） | 分支、endpoint、PG16、表结构、seed、runtime 权限已查 |
| PG16 local DSN read-only preflight | HOLD | 等待用户在 Windows 提供本地隐藏输入的 RC3.6 runtime DSN |
| PG16 real business gate | HOLD | 必须先 read-only PASS，再由用户输入精确授权短语，才会写入唯一 `rc36gate-*` 测试记录并执行一次应用层 Worker retry fault injection |
| RENDER | HOLD | PG16 真实业务 PASS 后再部署独立候选 |
| BROWSER_REAL_E2E | HOLD | Render 独立候选部署后再执行 |

Neon connector 本轮只执行了 SELECT 查询；未运行 MRP、未插入业务记录、未运行 Worker、未执行故障注入、未执行迁移或 DDL。

## 6. Windows 一次性执行

文件：`RUN_RC36_PG16_ONE_SHOT.ps1`。  
默认自动通过 `py.exe -3.14` 定位 Python 3.14；也支持 `-PythonExe` 指定完整解释器路径。自动建立独立 `.rc36-pg16-venv-py314`，安装 `requirements-rc36-pg16-gate.txt`，执行完整 LOCAL 回归、Node 语法检查，再请求 RC3.6 Neon runtime DSN。

在 RC3.6 完整源码根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC36_PG16_ONE_SHOT.ps1"
```

脚本只接受以下连接身份：

- Host：`ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech`
- Database：`industrial_v19b_preview`
- Role：`v19b_app_runtime`
- SSL：`sslmode=require` 或更严格
- 非 pooler endpoint

第一次隐藏输入时，从 Neon 项目 `industrial-ai-paas-v19-version-b-preview` 的分支 `rc36-pg16-isolated-20261106` 选择数据库 `industrial_v19b_preview` 和角色 `v19b_app_runtime`，复制 connection string。不要使用 `v19b_preview_owner`、`cloud_admin`、RC3.5 分支、default/preview 分支或 pooler。

只读预检查 PASS 后，脚本会询问是否授权隔离业务 DML 与单次 Worker fault/retry。**只有输入完整短语** `RUN_RC36_ISOLATED_PG16_WRITES_AND_FAULT_TESTS` 才执行。直接回车则只结束只读检查，业务门禁保持 HOLD。无论何种情况，脚本都不运行迁移/DDL、不修改 mock ERP/WMS 源表、不调用外部 MES/SRM/ERP，也不触碰 RC3.5 父分支。

证据目录：`release_evidence\rc36\`；脚本结束时自动打包 `RC36_PG16_EVIDENCE.zip`。重点文件：`GATE_STATUS.json`、`PG16_READONLY_RESULT.json`、`PG16_READONLY.log`、`PG16_BUSINESS_RESULT.json`、`PG16_BUSINESS.log`、`RC36_GOLDEN_SCENARIOS_PG16.json`、`PLAN_EVIDENCE_*.json`、`SUPPLY_EXPLANATIONS_*.json`。

**当前总体状态仍为 HOLD**：已完成独立分支只读结构/权限预检查与 PG16 gate 准备，尚未执行 Windows 本地 DSN 预检查及真实业务 DML/Worker/A-B 门禁。Render 暂不启动。

### 可重复的离线种子回放

已将只读获取的 RC3.6 分支种子快照保存为 `release_evidence/rc36/PG16_BRANCH_SEED_SNAPSHOT.json`，并新增 `gates/rc36_offline_seed_replay.py`。该脚本不连接数据库，使用当前 Version A 原生 JS 引擎、B 侧 MRP 分配器及 PG16 证据校验函数，对 A/B/C/D 四个场景进行可重复回放。当前四场景均为：snapshot recompute MATCH、supply source caps MATCH、A/B numeric MATCH、order-level Pegging MATCH。结果保存于 `release_evidence/rc36/PG16_OFFLINE_SEED_REPLAY.json`。

此结果严格标记为 `PASS_OFFLINE_ONLY`，不代表 Neon PG16 真实业务门禁 PASS；真实 gate 仍会从用户 DSN 读取当时的数据库快照并验证持久化行。
