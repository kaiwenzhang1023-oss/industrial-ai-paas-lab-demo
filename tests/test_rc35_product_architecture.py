from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'enterprise_workbench/site'

def test_rc35_navigation_matches_approved_information_architecture():
    html=(SITE/'index.html').read_text(encoding='utf-8')
    for label in ['经营总览','销售订单','BOM 与库存','MRP 计划','SRM 采购协同','MES 生产协同','需求与供应追溯','智能履约决策','跨系统映射校验','工作流与审计','系统设置','运行环境说明']:
        assert label in html
    assert 'MRP 企业执行中心' not in html

def test_rc35_mode_entry_is_business_first_and_separated():
    app=(SITE/'app.js').read_text(encoding='utf-8')
    enterprise=(SITE/'enterprise-console.js').read_text(encoding='utf-8')
    assert '浏览器本地模拟' in app and '企业持久化闭环' in app
    assert 'data-rc35-mode="enterprise"' in app
    assert "document.addEventListener('rc35:enterprise-mode',e=>" in enterprise
    assert '两种方式相互独立，不进行结果转换' in enterprise

def test_rc35_enterprise_exception_matrix_is_snapshot_derived():
    js=(SITE/'enterprise-console.js').read_text(encoding='utf-8')
    assert 'function enterpriseExceptionPanel(lines)' in js
    assert "data-action=\"bucket\"" in js
    assert "data-action=\"exception-filter\"" in js
    assert 'state.run?.lines' in js

def test_rc35_receipt_audit_and_material_explorer_have_feedback_hooks():
    js=(SITE/'enterprise-console.js').read_text(encoding='utf-8')
    assert 'vbc-card-receipt' in js and 'vbc-card-audit' in js
    assert 'vbc-material-explorer' in js
    assert '追溯订单需求来源' in js
