# Industrial AI PaaS Lab RC3.5 RC3 — 集中开发候选

**状态：LOCAL TEST PASS / PG16 + BROWSER + CLOUD HOLD。不是最终发布。**

## 已落地

1. 新增 `enterprise_workbench/rc35_planning.py`：按日/周对真实持久化计划行计算毛需求、净补货、计划到货、确认到货；按物料提前期和计划释放日解释风险，保留订单直接来源分配。
2. 新增受身份权限保护的 `GET /api/v1/version-b/enterprise/planning/time-buckets/{run_id}?granularity=day|week`，复用 PostgreSQL 原始快照指纹校验和租户单据校验。
3. 企业 MRP 矩阵改为调用后端，不再把 `net>0` 错标为已证实的实际缺料；支持按日/周、风险过滤、单元格明细和来源解释。
4. 新增 As-Is / To-Be / Trade-off 真实后端 What-if 三栏分析区域、参数调整、隔离重算、复制候选 JSON、丢弃本地候选；明确不生成企业审批或采购指令。
5. 保留 RC2 的历史审计中心、角色权限和原有审批、Outbox、Worker、回执机制；不更改 RC3.4 冻结基线。
6. 新增时区计算和 API 权限测试、单次 Windows PowerShell 本地门禁脚本。

## 计算边界

- `net` 是净补货需求，不等于真实缺料；`planned` 是计划到货而非供应商确认。
- `sources` 是来源分配，非全链路精确 Pegging；生产能力按无限产能假设，不能证明 MES 排程可行。
- `BLOCK` 表示计划释放日早于快照日的提前期风险，**不代表已证实停工**。
- AI 三栏使用确定性的隔离 What-if 计算，不冒充大模型自主决策。

## 验收

- Python tests：44 passed（本地）
- Node `--check`：通过
- PG16 真实数据库集成：**HOLD（未执行）**
- 浏览器交互、Render、Neon：**HOLD（未执行）**

## 下一阶段必须完成

- 真正的跨层 Pegging 与订单延期影响（当前来源仅为单层分配）；供应确认及成本/产能约束。
- 持久化候选方案、审批与候选版本绑定、Outbox 与补偿事件状态机，禁止将本地候选直接视为已批准变更。
- 批量异常处置、G01/G02/G03 同快照黄金场景、浏览器真实 E2E、PG16 故障注入和统一发布门禁。

## Windows 一次性本地检查（仅当需要人工验收时）

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC35_RC3_ONE_SHOT_LOCAL_GATE.ps1" -Python "D:\Anaconda3\python.exe"`

不要求现在执行；本包仅开发候选。
