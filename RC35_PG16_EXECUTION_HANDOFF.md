# RC3.5 专属 PG16 一次性门禁

状态：**LOCAL PASS / PG16 LIVE HOLD（等待 Windows Python 3.14 + 隔离分支执行）**。

- 在 RC3.5 Final Functional Gate 完整源码上派生新门禁，未修改 RC3.4 历史。
- 专属脚本 `tests/rc35_isolated_pg16_gate.py`，只允许 Neon PG16 隔离分支 `rc35-final-gate-isolated-20261105` 的端点 `ep-patient-wind-bbme3mck`、数据库 `industrial_v19b_preview`。
- 增加 `proposals` 持久化表快照检查，以及 G01/G02/G03 实际 PG16 MRP 计算结果导出：物料总需求、净补货、计划补货、订单来源分配、数量守恒。
- 本地 Python 3.13 pytest **62/62 PASS**；脚本编译 PASS。
- Neon 只读查询确认 PG16.15、RC3.5 proposals 表和已有工作流/Outbox/审计表存在。此前已有的两条 MRP 记录均有 8 种物料、2 张订单、总需求 1580、净补货 480、计划补货 490；它们不是 G01/G02/G03 的执行证据。

## 用户执行一次

1. ZIP 解压至 Windows Version B 工作目录下新子目录，不覆盖原版。
2. Neon Console 选项目 `industrial-ai-paas-v19-version-b-preview` → 分支 `rc35-final-gate-isolated-20261105` → 数据库 `industrial_v19b_preview`，复制 connection string。
3. 在源码根目录执行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\RUN_RC35_PG16_ONE_SHOT.ps1 -PythonExe 'D:\Anaconda3\python.exe'`。
4. 在隐藏输入框粘贴连接字符串；确认仅向隔离分支写入测试租户后输入 `RUN_RC35_ISOLATED`。
5. 回传 `release_evidence\rc35_pg16_enterprise\RESULT.json`、`RC35_GOLDEN_SCENARIOS_PG16.json`（若生成）及末尾 `RC35_PG16_GATE_*` 输出。不要提供数据库连接字符串或密码。

## 范围与未完成项

- G01/G02/G03 仍映射已有 B/C/D 模拟场景，不是三套独立的真实工厂数据。
- Worker 为 `INTERNAL_VALIDATION_ONLY`，不代表真实 MES/WMS/SRM 写入。
- PG16 端到端写入、故障注入、浏览器与 Render 门禁尚未执行，不能宣称 Final PASS。
