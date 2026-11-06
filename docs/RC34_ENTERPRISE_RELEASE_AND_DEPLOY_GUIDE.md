# RC3.4 企业级收尾候选：部署和统一门禁

## 不可修改的基线
- Version A V1.9 静态版，不改动；本包引用的 `enterprise_workbench/site/engine.js` 为经验证的冻结 A RC8 引擎副本。
- Version B RC2 冻结 GitHub/Render/Neon 分支，不覆盖、不升级、不执行迁移。
- 只能操作 RC3.4 **候选** GitHub 分支 `v19-version-b-enterprise-ux-rc31-candidate` 和其 Render **候选**服务。
- 不创建 Docker 容器、Neon 分支或数据库；不注入对其他连接有影响的故障。

## GitHub 最小更新（需要登录用户在网页执行）
仅在候选分支的 `enterprise_workbench/site/` 目录覆盖 `index.html` 和 `enterprise-console.js`。
后端 `rc2.py`、`rc4.py`、`worker.py`、`g3/`、`g4/` 和 CSS 与候选分支当前 blob 哈希一致，不必上传。不要向默认分支/RC2 分支提交。

最小上传 ZIP：`V19B_RC34_GitHub_Candidate_2File_Upload_20261105.zip`（单独链接）。
建议提交消息：`RC3.4 enterprise candidate: session recovery and version marker`。
提交后用 Render 候选服务 `srv-dbllmt15efls73e4qj60` Manual Deploy 更新到候选分支最新提交，autoDeploy 保持关闭。**旧部署 ID dep-dbm142a3ep3s739ndiq0 不是更新后的部署。**

## Windows 一次性验收
本机 Python 3.14，Node.js，Playwright Chromium；已经成功安装的 Chromium 无需重复下载。先在 PowerShell 会话中设置隔离 Neon 分支对应的 `V19B_RC34_ISOLATED_TEST_DATABASE_URL` 环境变量（不要回传到聊天、写进 ZIP 或日志）。该连接串必须指向隔离 Neon endpoint `ep-twilight-violet-bb8pm1v6` 和数据库 `industrial_v19b_preview`；其余主机自动拦截。

在新 ZIP 解压后的 `Industrial_AI_PaaS_Lab_V19B_RC34` 根目录，且**仅在已确认候选 Render 部署新提交后**执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC34_ENTERPRISE_ONE_SHOT.ps1" -PythonExe "D:\Anaconda3\python.exe" -RunIsolatedPG16 -RunLiveBrowser
```

- `-RunIsolatedPG16` 是显式授权，仅为新测试租户创建 4 个 MRP 运行、审批/回执/审计/对账记录；不会修改 `mock_erp`、`mock_wms` 或旧 RC2 分支。
- Worker 故障为测试进程内单次处理失败注入；PG16 故障为**自身连接的 statement_timeout**，不杀其他连接/数据库。**这不等价于 Neon 节点级宕机恢复。**
- `-RunLiveBrowser` 直接打开候选 Render 实际页面，创建一笔新的独立访客租户 MRP；验证五步流程、刷新恢复、审批、内部执行回执、What-if、动态 A/B、第二访客 404；不做外部 ERP/MES/SRM 写入。
- 不传两个开关仅复跑不变的本地测试 + 网络只读健康检查，仍会 HOLD；不要反复执行已 PASS 的门禁。

证据：
- `release_evidence/pg16_enterprise/RESULT.json` + `WHAT_IF_PG16_BEFORE.json`、`WHAT_IF_PG16_AFTER.json`；
- `release_evidence/live_business/RESULT.json` + 4 张阶段截图；
- `release_evidence/FINAL_RELEASE_GATE_RESULT.json` + `python_pytest.log`、`browser_mock.log` 等；
- `FINAL_SOURCE_SHA256.json` 只约束稳定源码；运行期间追加/更新的测试证据不参与源码冻结哈希。

## 最后一道冻结分支隔离门禁
真实 PG16 新测试产生 4 个 `run_id` 后，由助手通过已连接 Neon **只读 SQL** 在冻结分支 `br-patient-surf-bb9nyu0h` 独立确认这四个 ID 均不存在。**本候选版不会向冻结 RC2 发出写请求，也不会自动填写虚假的 PASS。**在独立核验前 `frozen_rc2_protection` 保持 HOLD。

## 权限陈述限定
- 角色矩阵在**私有多身份 FastAPI 测试应用** + 真实隔离 PG16 上测试，适用于 API 角色授权逻辑。公开 Render 访客会话仍固定 `admin`，不能据此称公开演示平台已经提供可登录的五角色账号体系。
- PG16 表未启用原生 RLS；当前租户隔离在服务端 API 层实现，不应表述为数据库原生行级安全防护。
- 对账 `DIFFERENT` 只要带真实引擎来源、同输入指纹和逐字段差异原因，可以判定对账机制有效，但业务结果不等于 A/B 完全一致；不能把 DIFFERENT 标注成 MATCH。
- 场景 C 是客户交期顺延 7 天，不是 MES 产能排程；场景 D 是 BOM 首行用量异常，不是跨系统映射错误。Worker 结果仅 `INTERNAL_VALIDATION_ONLY`。
