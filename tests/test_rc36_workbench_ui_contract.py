"""Static source contracts for RC3.6 browser UI; not a browser E2E claim."""
from pathlib import Path
import subprocess

JS=Path(__file__).resolve().parents[1]/"enterprise_workbench/site/enterprise-console.js"
CSS=JS.with_suffix(".css")

def test_workbench_js_syntax():
    result=subprocess.run(["node","--check",str(JS)],capture_output=True,text=True)
    assert result.returncode==0, result.stderr

def test_two_mode_switch_and_session_independence():
    js=JS.read_text(encoding='utf-8')
    assert 'data-action="mode-local"' in js
    assert 'rc35:local-mode' in js and 'rc35:enterprise-mode' in js
    mode=js.split("if(name==='mode-local')",1)[1].split("if(name==='line-kind')",1)[0]
    assert 'clearSession(' not in mode and 'logout' not in mode

def test_five_row_explorer_interactions():
    js=JS.read_text(encoding='utf-8')
    for text in ['物料计划与供需追溯','data-action="line-kind"','data-bind="lineSearch"','vbc-table-wrap','data-action="page-next"','data-action="line-export"','data-action="line-detail"','data-action="line-trace"','data-action="line-reset"','data-line-index','vbc-selected']:
        assert text in js,text
    assert 'vbc-selectable' in CSS.read_text(encoding='utf-8')

def test_quantity_semantics_and_no_fake_order_net():
    js=JS.read_text(encoding='utf-8')
    for text in ['单位未核实','非整数','—（未提供订单级净算）','—（未生成）','净需求','未确认计划供应分配','外部履约状态']:
        assert text in js,text
    assert '净补货' not in js
    assert '总净需求量</span>' not in js
    assert '计划供应数量</span>' not in js

def test_export_retains_raw_values_and_snapshot():
    js=JS.read_text(encoding='utf-8')
    assert 'snapshot_hash:state.overview?.snapshot_hash' in js
    assert 'rows=visibleRows().map' in js
    assert 'order_net_requirement:pegging?null' in js
