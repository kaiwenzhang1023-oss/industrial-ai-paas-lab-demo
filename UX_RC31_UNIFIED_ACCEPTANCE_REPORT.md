# Version B 企业执行中心 UX RC3.1｜集中验收报告（隔离部署 HOLD）

**日期：2026-11-04**  
**基线：** `v19-version-b-preview`，commit `ea20d05f24f9d641442339dcff3d1b48e063d091`  
**综合判定：** `CANDIDATE_OFFLINE_PASS / CLOUD_DEPLOY_HOLD / UX_LIVE_PG16_HOLD`

## 本轮已完成

1. 将此前的 UX RC3 完整候选源码作为实际工作树，核实 `enterprise-console.js` / `enterprise-console.css` / 入口 `index.html` 的五步企业闭环，保留旧 A 风格业务模拟模块。
2. 修复跨 MRP 运行切换时旧 `commandId`、旧命令和回执可能残留的问题；对总览和命令返回执行 `run_id` 一致性校验。**仅改动 UX 前端与对应浏览器测试，不修改 RC2 业务后端。**
3. 后端原有测试 `14 passed`；真实 Chromium + mock HTTP 前端交互 `14/14 PASS`（新增切换运行回执隔离）；Node 语法检查 PASS。Mock HTTP 测试不能证明真实云端成功。
4. 与 GitHub 冻结分支逐项对照 7 个关键文件的 Git blob SHA，均一致：`enterprise-status.js`、`rc2.py`、`rc4.py`、`worker.py`、`app.js`、`preview_cloud/app.py`、`Dockerfile.version-b-preview`。入口页改动属预期。
5. Neon PG16 只读实查：PostgreSQL `16.15`；历史 RC2 留存 **2** 条运行、**2** 条审批、**2** 条 Outbox、**2** 条持久化执行回执、**4** 条审计；两笔都是 `APPROVED → EXECUTED_INTERNAL / Outbox DONE / attempts=1`，连接缺失计数 0。这些是 **RC2 历史持久化证据**，而非 UX RC3.1 候选云端闭环执行结果。

## 仍未完成（不可标记 PASS）

| 门禁 | 状态 | 原因/证据 |
|---|---|---|
| 独立 UX GitHub 分支 | **HOLD** | GitHub connector `create_branch` / `create_blob` 均返回 403 `Resource not accessible by integration` |
| 独立 Render 候选部署 | **NOT CREATED** | 没有包含 RC3.1 的 GitHub 分支，不能安全部署源码 |
| 候选独立 Neon 分支 | **NOT CREATED** | 避免在没有可运行候选服务时额外消耗免费计算额度；原 Neon preview 保持不变 |
| RC3.1 真正 HTTP → PG16 → Worker → 回执全链路 | **NOT EXECUTED** | 尚无 RC3.1 独立候选服务；不能将历史 RC2 SQL 证据冒充候选验收 |
| 云端浏览器正常/驳回/故障场景 | **NOT EXECUTED** | 同上 |

## 保护约束

- 线上 Version B 冻结 Render 服务 `industrial-ai-paas-v19-version-b-preview` 当前记录来源为 `ea20d05`；本轮未改动该服务、环境变量或部署。
- Version A 完全未修改。
- 所有验收证据不包含 Neon 连接字符串、令牌、Render 机密。
- 任何 Worker 执行均限定为内部校验；没有生产 ERP/MES/SRM 写入。

## 实际可执行的后续发布路径（最小人工步骤）

压缩包根目录自带 `RUN_PUBLISH_UX_RC31_CANDIDATE.ps1`，会自己从冻结分支 shallow clone 到 Windows TEMP，检查固定 SHA，复制**仅五个允许变动的 UX 文件**，创建独立 `v19-version-b-enterprise-ux-rc31-candidate` 分支，提交并推送。它不依赖用户现有文件夹是否有 `.git`，也绝不推送到 `main` 或 `v19-version-b-preview`。缺少 Git 作者信息时会在脚本内询问一次；GitHub 登录由 Git Credential Manager 完成。

在解压出的源码根目录执行一次：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_PUBLISH_UX_RC31_CANDIDATE.ps1"
```

**发布检查必须真实返回 `V19B_RC31_CANDIDATE_PUBLISH=PASS` 后方可继续。** 若 GitHub 网络或权限失败，状态保持 HOLD；不能仅凭 `Write-Host` 或脚本尾部文本宣称成功。

候选分支实际推送后，可通过 Render 创建**全新** Free Web Service：`industrial-ai-paas-v19b-ux-rc31-candidate`，使用 Docker `./Dockerfile.version-b-preview`，指定新候选分支，关闭自动部署。数据库应使用与历史预览分开的 Neon 分支和独立受限凭据，`DATABASE_URL` 和强度足够的 `PREVIEW_SESSION_SECRET` **仅在 Render 私有环境配置，不写入 ZIP**。候选 Render 完成部署后执行 `RUN_V19B_UX_RC31_LIVE_E2E.py`（会强制拒绝在现有正式 RC2 URL 上进行测试），按 `UX_RC31_LIVE_E2E_EVIDENCE.json` 检查。

真实云端验收必须同时满足：创建 MRP、跨租户隔离、审批、Outbox、Worker、回执、审计、驳回与重复审批拒绝，并补充浏览器访问和 Render 日志证据。**未满足前绝不替换 Version B 正式页面。**
