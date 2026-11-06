# RC3.5 Neon PG16 DSN Parser Fix RC1 — 2026-11-05

## 本地已验证
- Python 门禁解析测试：14 PASS
- 本地 tests/ 全量回归：76 PASS（本环境）
- 本次未连接 Neon；PG16 门禁与黄金场景仍为 HOLD，不能部署 Render。

## 修复
- 支持纯 `postgresql://` / `postgres://` URL、首尾空白、整串引号、Neon 复制的 `psql '<URL>'` 和 `psql -d <URL>`。
- 保持独立端点 `ep-patient-wind-bbme3mck.*.neon.tech` 与数据库 `industrial_v19b_preview` 的白名单；拒绝 pooler、其他端点和数据库。
- 报告仅输出安全错误代码，不写入连接字符串或密码。
- PowerShell 5.1 的脚本修复版已包含在完整源码 ZIP 内。

## 使用
1. 解压完整 ZIP 至新的目录，勿覆盖旧版。
2. 在解压后的源码根目录运行：
   `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC35_PG16_ONE_SHOT_FIXED_PS51.ps1" -PythonExe "D:\Anaconda3\python.exe"`
3. Neon 控制台选择 branch `rc35-final-gate-isolated-20261105`、database `industrial_v19b_preview`、role `v19b_app_runtime`、pooling OFF；隐藏输入中粘贴 URL 或完整 `psql '<URL>'` 命令。
4. 仅在确认是上述隔离分支后输入 `RUN_RC35_ISOLATED`。
5. 回传 `release_evidence\pg16_enterprise\RESULT.json` 和 `RC35_GOLDEN_SCENARIOS_PG16.json`，不回传凭据。

## 限制
- 本次修复只解决连接字符串解析/白名单诊断。不能保证后续 PG16 表权限、数据契约、真实业务计算通过；必须以实际门禁报告为准。
- 现有 FINAL_SOURCE_SHA256.json 为原始基线记录；本修复另生成 RC35_DSN_FIX_SHA256.json 记录变更，避免冒充原冻结清单。
