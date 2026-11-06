# RC3.4 Business-First 浏览器验收脚本修复

根据用户 RESULT(2).json：candidate_http、brand_rc34、session_connected、mrp_created、refresh_run_restored 均 PASS；原脚本等待旧版 `data-action=nav` 按钮而失败。

本修复仅替换 `tests/live_business_workflow_gate.py`，使用当前业务首页存在的 `approve`、`dispatch`、`receipt`、`refresh` 控件，保存阶段截图；失败时新增 `FAIL_AT_STEP.png`。

**无需 GitHub 提交、Render 部署或 Neon 凭据；不修改业务代码。** 本脚本尚未在用户的真实 Windows/Render 环境执行，结果必须按 RESULT.json 判断。

解压后把 `tests/live_business_workflow_gate.py` 覆盖原源码根目录下同名文件。原 PowerShell 脚本不变：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RUN_RC34_LIVE_BUSINESS_GATE.ps1" -PythonExe "D:\Anaconda3\python.exe"
```

该脚本会新建独立访客租户的测试 MRP。若失败不要反复运行，回传 RESULT.json 和 FAIL_AT_STEP.png。
