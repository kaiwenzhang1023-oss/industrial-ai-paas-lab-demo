# RC3.4 PG16 企业级集成门禁：用户执行说明

## 目标环境（固定，不得更换）
- Neon Project：`super-glade-55757112`
- Existing isolated branch：`v19b-ux-rc31-isolated-acceptance`
- Endpoint：`ep-twilight-violet-bb8pm1v6`
- Database：`industrial_v19b_preview`
- PostgreSQL：16.x

不创建 Neon branch，不创建 Docker 容器，不运行 schema migration，不连接冻结 RC2 分支。

## 脚本会做什么
- 使用本地 FastAPI 测试应用挂载实际 RC2/RC4 路由，连接真实隔离 Neon PG16。
- 创建唯一 `rc34gate-*` 测试租户和少量 MRP/审批/Outbox/回执/审计/对账记录。
- 测试 viewer/planner/approver/operator/admin API 权限矩阵、跨租户 404、未认证 401。
- 并发重复审批、幂等冲突、Worker 应用层失败→RETRY→恢复 DONE、SKIP LOCKED 双 worker、租约过期接管及旧 worker stale ack 拒绝。
- 执行 Version A 原生 RC8 JavaScript 与 Version B PG16 持久化结果的 A/B/C/D 同快照动态对账。
- 对 stock/receipt/due 三种 What-if 分别计算 PG16 运行相关表前后行数和 SHA256。
- 执行单连接 `statement_timeout`，随后验证新连接恢复。

## 写入边界
- 只写入隔离分支中新建的唯一测试租户与测试 Run；测试记录保留作为证据，不自动 DELETE。
- 不写入/更新 `mock_erp`、`mock_wms` 业务源表；脚本会比较测试前后源表哈希。
- 不执行 TRUNCATE、DELETE、DDL、migration；不访问 Version A/冻结 RC2；不执行外部 ERP/MES/SRM 命令。
- Worker 故障是应用层单任务失败注入与 lease expiry，不是 Neon 节点宕机模拟。
- 权限矩阵是 API 层角色校验，不代表 PostgreSQL 原生 RLS 已启用。
- 如果 A/B 对账出现 DIFFERENT，会保留真实差异和原因，并将精确结果一致性标记 HOLD，不会伪报 MATCH。

## 你只需要执行一次
在完整源码根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC34_PG16_ENTERPRISE_ONLY.ps1" -PythonExe "D:\Anaconda3\python.exe"
```

脚本会：
1. 检查 Python 3.14、FastAPI/httpx/psycopg、Node.js。
2. 如果当前 PowerShell 会话没有连接字符串，提示从 Neon Console 复制上述**既有隔离分支**的连接字符串；输入为隐藏模式，不回传聊天。
3. 要求输入 `RUN_ISOLATED_PG16_TESTS` 作为明确写入确认。
4. 自动检查连接串 endpoint 与 database allowlist；不匹配即停止，不执行 SQL 写入。
5. 执行 PG16 集成门禁并生成证据。

不要把 Neon connection string、密码或 token 发到聊天，也不要写入 `.env`、ZIP 或日志。

## 回传给助手
只需回传：
- `release_evidence\pg16_enterprise\RESULT.json`
- 若存在 `failed_check`，再回传对应的脱敏错误日志/行号。

`WHAT_IF_*_BEFORE.json` 和 `WHAT_IF_*_AFTER.json` 会用于核对 What-if 数据库副作用；如果报告指出不一致，请一并回传这六份文件。

## 结果解释
- `RC34_ENTERPRISE_PG16=PASS`：本脚本范围内的真实 PG16/API/Worker/A-B/What-if 门禁通过；不代表最终 Release Gate 自动 PASS。
- `FAIL`：存在真实失败或环境/契约异常，按 `failed_check` 与 traceback 行号修复。
- `HOLD`：未提供正确连接串或未确认写入，数据库没有被测试脚本访问/修改。
