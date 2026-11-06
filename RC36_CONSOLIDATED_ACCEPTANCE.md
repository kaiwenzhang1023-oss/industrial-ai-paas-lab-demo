# RC3.6 集中开发候选 — 验收记录

## 基线
- 用户上传：Industrial_AI_PaaS_Lab_V19B_RC35_PG16_Parser_Fix_RC1.zip（完整源码，不采用 Render Isolated Candidate 精简包）
- 原始 RC3.5 源码保持不变，RC3.6 在独立工作树修改。
- 当前会话没有可读取的前一轮 RC3.6 工作树，故无法证明此前声称的 97 passed 或逐文件复用；已重新核验当前上传源码的 76 passed。

## 本轮已实现（实际代码）
- 时间桶：冻结物料主数据单位优先，行单位不一致直接拒绝；禁止静默跨单位加总。
- 订单/上游来源：每个时间桶保留逐需求日期与数量的来源证据，不将来源分配冒充供应商收货或完整跨层 Pegging。
- 拒绝负数来源分配；保持 Decimal 数量计算与日/周数量守恒。
- 旧版字段兼容，新增 `unit`、`source_allocations[].demand_dates` 与语义标记。
- 新增 5 项针对性回归。

## 实际验收
- Python pytest: 81 passed (当前沙箱 Python 环境；详见 RC36_LOCAL_GATE.log)
- PG16 真库集成: HOLD（本沙箱无用户本机 PG16 连接）
- Windows PowerShell 5.1 / Python 3.14.6: HOLD
- Render 预览: HOLD
- 浏览器完整交互: HOLD
- 六项整改全覆盖与整版冻结: HOLD（当前为部分实施候选，不冒充完成）

## 四阶段语义边界
1. 需求计算：净补货需求不是实际缺料。
2. 供应建议：计划收货不是供应商承诺或已确认到货。
3. 人工审批：不能以计划结果替代审批授权。
4. 内部执行与回执：内部指令/回执不代表外部履约。

未修改旧 PG16 迁移、Render、Neon、GitHub 或 RC3.5 冻结分支。
