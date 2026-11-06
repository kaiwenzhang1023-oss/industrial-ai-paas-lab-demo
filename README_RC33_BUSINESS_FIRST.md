# Version B RC3.3 · 企业业务单据化候选（未上线）

## 交付范围
- Version B 默认进入「MRP 企业闭环执行中心」，原浏览器模拟页面仍可从左侧访问。
- 中文业务状态、流程下一步提示、访客会话及内部执行边界说明。
- 状态驱动的计划单创建、查询、审批、内部校验、回执、审计操作。
- 物料需求净需求及计划供应来自当前后端单据行；不拼接 Version A 模拟数据。
- 审批意见模板、重置当前页面流程（不删除数据库记录）。
- 数据库审批、回执、审计事件呈业务卡片和时间线；技术报文折叠。
- 原始后端 API / PG16 / Outbox / Worker / MCP 接口未修改。

## 验收事实
- `node --check enterprise_workbench/site/enterprise-console.js`：PASS。
- `python tests/browser_enterprise_rc33.py`：9/9 PASS（Playwright Chromium，模拟 HTTP 响应，**非云端真实验收**）。
- `python -m pytest tests/test_preview_rc2.py -q`：14 PASS。
- 旧 `tests/browser_enterprise_rc3.py` 为旧五步骤 DOM 结构验收脚本，已被 RC3.3 新界面替代，不应再作为 RC3.3 的发布门禁。
- GitHub 候选提交、Render 部署、Neon PG16 新 Run ID 验收：**PENDING**。

## 安全和已知边界
- 访客 token 只保存在当前页面内存；刷新丢失身份，不可仅凭 Run ID 跨租户恢复。
- 本次不实现 localStorage 自动恢复，也不实现 Version A/B 两套 MRP 数据融合。它们需要单独的数据与会话契约验收。
- 审计时间线不伪造数据库事件，MRP 创建节点来自单据、回执节点来自回执，审计节点来自后端 events，已注明来源。
- UI 仅执行内部业务校验，不向真实 MES/SRM/ERP 写入。
- 未修改 Version A 或 Version B RC2 冻结服务。

## 网页上传
从冻结的 RC3.1 候选分支创建新分支 `v19-version-b-enterprise-ux-rc33-candidate`；在 `enterprise_workbench/site/` 上传 3 个文件：`index.html`、`enterprise-console.js`、`enterprise-console.css`。不上传整个 ZIP 到 GitHub 文件夹。

部署到独立候选 Render 时必须配置隔离 Neon PG16 DATABASE_URL 和独立 PREVIEW_SESSION_SECRET，不能覆盖 RC2 或 RC3.1 服务；上线后再做真实浏览器与 PG16 业务闭环验收。
