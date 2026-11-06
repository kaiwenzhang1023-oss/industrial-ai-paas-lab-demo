# Version B 企业执行中心 UX RC3｜离线统一验收报告

**候选：UX RC3（未发布）**  
**基线：`ea20d05` / `v19-version-b-preview`**

| 门禁 | 结果 | 证据 |
|---|---|---|
| 冻结源码一致性 | PASS | 原有文件中仅 `site/index.html` 变化；新增两个 UI 文件和测试证据；`enterprise-status.js` 保持原 SHA |
| RC2 后端回归 | PASS | `14 passed` |
| Browser UI · Mock API 合约 | PASS | 13/13 检查点：会话、MRP、追溯、审批、Worker、回执、审计、What-if、原静态模块、移动端与 JS 无报错 |
| 真实 PG16 端到端 | **NOT EXECUTED** | 本地无 Neon 预览数据库事务访问 |
| Render 在线部署 | **NOT EXECUTED** | 仍为冻结 RC2 |
| GitHub UX 分支 | **HOLD** | 当前 connector 创建分支 HTTP 403，用户 Windows 目录无 `.git` |

## 接口校验范围

- 会话：`POST /api/v1/version-b/preview/session`，`GET /api/v1/version-b/enterprise/me`
- MRP：`POST /mrp/runs`, `GET /mrp/runs/{run_id}`
- 业务状态：`GET /review/overview/{run_id}`
- 审批与执行：`POST /decisions`, `POST /worker/dispatch`
- 回执：`GET /commands/{command_id}`
- 高级工具：`POST /what-if`、`/reconciliation/...`、`/mcp/...`

## 特别说明

本轮浏览器证据来自受控模拟 HTTP 回应，用于验证用户可见状态和前端调用协议；**不能取代实际云端数据库和网络故障注入**。界面并不把 A 版的浏览器 MRP 自动写入 B 版的 PostgreSQL 数据库，只有本界面中的「创建 PostgreSQL MRP」会启动持久化运行。

验收状态：**CANDIDATE_OFFLINE_PASS / LIVE_GATE_HOLD**。
