# Industrial AI PaaS Lab — Version B Enterprise Console UX RC3

## 本版状态（2026-11-04）

**离线候选版，尚未部署。** 本包以 `v19-version-b-preview` / `ea20d05f24f9d641442339dcff3d1b48e063d091` 对应 RC2 完整源码为基础，保留当前企业服务所需全部文件。已完成 14 项原有后端回归和 13 项使用模拟 HTTP 合约的浏览器端检查。**未运行真实 Neon PG16 / Render 线上回归，不得将此版本标记正式云端验收通过。**

## 业务体验升级

Version B 左侧新增「企业执行中心 · Version B」入口，从独立演示会话开始，沿着 **MRP 运行详情 → 审批中心 → 执行监控 → 回执详情 → 审计时间线** 五步完成全程导航。MRP 表格、Pegging、快照证据、审批理由、Outbox 状态、Worker 尝试次数、回执字段和审计事件直接展示为可读卡片/表格/时间线。高级工具保留隔离 What-if、冻结基准和动态 A/B 对账、MCP。返回不确定性/失败时提示真实 API 错误，不造假成功状态。

## 技术边界

- 核心后端 `enterprise_workbench/rc2.py`、`rc4.py`、`worker.py`、`preview_cloud/app.py`、数据库迁移均未改动。
- 原有静态业务模拟 JS、CSS 和数据也均保持字节一致，仅更新入口 `enterprise_workbench/site/index.html`，新增 `enterprise-console.js` 和 `enterprise-console.css`。
- 当前主闭环采用既有 RC2 / RC4 APIs。被替换的旧 `enterprise-status.js` 仍保存在源码中，但首页不再加载，以免出现两套企业面板。
- 真实运行与审批数据仍由独立 Neon/PostgreSQL 储存，本候选页面本身不缓存访问令牌，也不连接真实 ERP/MES/SRM。
- 新访客会话隔离；Run ID 仅在当前租户能读取。刷新网页后临时令牌丢失，不能跨会话恢复旧租户数据。

## 文件

- `enterprise_workbench/site/index.html`：加载新企业控制台。
- `enterprise_workbench/site/enterprise-console.js`：五步可视化 UI，真实 API 交互。
- `enterprise_workbench/site/enterprise-console.css`：统一布局、状态卡片、响应式样式。
- `tests/browser_enterprise_rc3.py`：mock 合约浏览器回归。
- `evidence/`：浏览器测试截屏（注意不是云端实测截图）。
- `UX_RC3_GATE_RESULT.json`：验收状态。
- `UX_RC3_FILE_SHA256.txt`：文件哈希。

## 后续上线门禁（目前 HOLD）

1. 创建独立 GitHub UX 分支；此环境连接器写入返回 403，本机指定目录也不是 Git 工作树，因此**分支并未创建**。
2. 将本包内容提交到 UX 分支，Render 部署候选预览而非替换现有 RC2。
3. 使用真实 Neon PostgreSQL 对 `POST /mrp/runs` → `POST /decisions` → `POST /worker/dispatch` → `GET /commands/{command_id}` → `GET /review/overview/{run_id}` 完成端到端核验和浏览器状态展示。
4. 验证跨租户 403/404、异常 Worker、拒绝审批、重复幂等请求、刷新会话和旧静态页面回归。
5. 只有线上门禁 PASS 后才能发布新的 Version B 简历链接。

此包**不含**任何 Neon/Render 凭据。

## RC3.1 集中验收补充（2026-11-04）

- 发现并修复：同一访客租户查询另一笔 MRP 时，旧 `commandId` / 回执可能残留。现在 `fetchRun` 与 `fetchOverview` 会清理并校验运行号，`fetchCommand` 再校验回执对应的 `run_id`。
- 新增浏览器场景「切换 Run ID 后不能串单显示上一笔回执」，完整 Mock API 浏览器回归 **14/14 PASS**。
- RC2 原有后端回归 **14 passed**，Node JavaScript 语法 **PASS**。冻结 RC2 的 `enterprise-status.js`、`rc2.py`、`rc4.py`、`worker.py`、`preview_cloud/app.py`、`app.js`、Dockerfile 的 Git blob SHA 与 GitHub 上 `ea20d05` 逐项一致。
- 只读 Neon PG16 证据：`16.15`，2 条运行、2 条审批、2 条 Outbox、2 条回执、4 条审计；两条运行均 `EXECUTED_INTERNAL`，对应 Outbox `DONE`，`attempts=1`，回执存在，外部 ERP/MES/SRM 执行并未发生。这属于**历史 RC2 在线数据核对，绝不是新 RC3.1 的线上端到端通过**。
- 本轮无法直接创建新的 GitHub 分支或 Git blob：GitHub connector 均返回 **403 Resource not accessible by integration**。也无法通过该容器发出到 GitHub/Render 的外部网络请求。**未创建候选 Render 服务、未创建新的 Neon 分支、未执行候选版 LIVE E2E、未替换现有预览。**
- 为避免让用户再手动找 `.git`，提供 `RUN_PUBLISH_UX_RC31_CANDIDATE.ps1`：从冻结提交一次性克隆到临时目录、仅复制 UX 五个受控文件、创建新分支并推送。不会 push 到 `main` 或 `v19-version-b-preview`；仅最后 GitHub 推送成功才输出 PASS。
- 另提供 `RUN_V19B_UX_RC31_LIVE_E2E.py`，待独立候选 Render 服务部署后运行。该脚本明确拒绝在正式 RC2 URL 上执行写入测试，覆盖运行、审批、Worker、回执、审计、跨租户拒绝、重复审批拒绝以及驳回路径。
- **最终门禁：`CANDIDATE_OFFLINE_PASS / CLOUD_DEPLOY_HOLD / UX_LIVE_PG16_HOLD`。**
