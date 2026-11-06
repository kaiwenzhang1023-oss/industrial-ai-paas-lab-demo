# RC3.4 企业级剩余门禁：集中开发候选报告（非 Release PASS）

## 已完成
- 从上次 RC3.4 HOLD Closure 完整工作树延续开发，修复 `enterprise_workbench/site/index.html` 左侧 RC3.2 → RC3.4。
- 新增 `tests/live_business_workflow_gate.py` 与 `RUN_RC34_LIVE_BUSINESS_GATE.ps1`，覆盖真实候选 Render 浏览器创建 MRP、同标签页刷新恢复、审批、内部 Worker、回执与审计，跨租户 404、未认证 401，以及 What-if 前后 PG16 持久化摘要比较。
- 测试仅针对独立访客租户，结果输出 `release_evidence/live_business/RESULT.json` 和 4 张阶段截图。不会触碰冻结 RC2、不会注入数据库故障、不会执行外部 ERP/MES/SRM。
- 继承原 RC3.4 已通过的 25 项 pytest；本轮重新运行 25 passed。
- 原有真实 Render 桌面/移动端只读检查：用户已回传 PASS 证据；不重复要求截图。

## 尚未完成（HOLD）
- **新源码尚未提交 GitHub 候选分支或部署 Render**。当前 Render 仍是原 RC3.4 提交 `858e75ab756395e780150960540f22a6791eb414`；品牌标识新断言在旧部署上预期 FAIL。
- 新脚本尚未在真实 Render + Neon 执行；不得将脚本存在视为 PASS。
- PG16 故障注入与 Worker 恢复、角色 403 矩阵、并发幂等、Version A/B 全量动态同快照对账仍 HOLD。公共预览访客均为 admin，无法借此证明角色隔离；需要隔离角色环境。
- What-if 对比的是业务可见状态摘要，最终还需独立 SQL 前后计数/哈希核验。
- 本候选尚非 Final Release，禁止部署到冻结 RC2。

## 后续操作
先完成候选分支源码提交及独立 Render 候选部署，然后再在 Windows 3.14 环境执行：
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC34_LIVE_BUSINESS_GATE.ps1" -PythonExe "D:\Anaconda3\python.exe"`
不要在旧 Render 提交上重复执行本脚本。若失败仅回传 `release_evidence/live_business/RESULT.json` 和脱敏错误日志。
