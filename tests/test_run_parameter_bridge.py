"""Documented VBA ByRef transport contract, no native execution."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from cst_automation.run_parameter_bridge import prepare_run_parameter_query, parse_run_parameter_receipt


def wire(request, *, project=None, token=None, rid=None, rows=None):
    # VBA Hex$(AscW(character)) writes code-unit order: "A" -> "0041".
    hexd = lambda s: str(s).encode('utf-16-be').hex().upper()
    token = token or request['request_id']
    rows = rows if rows is not None else [('tone', '2.5'), ('side', '1')]
    return '\n'.join(['CST_RUN_PARAMETERS_V1', 'request\t'+token,
        'project\t'+hexd(project or request['project_resources']),
        'result_id\t'+(rid or request['result_id']), 'resolved\t1', 'count\t'+str(len(rows))]
        + ['param\t'+hexd(k)+'\t'+v for k,v in rows]+['END\t'+token, ''])


def test_macro_uses_documented_byref_and_checks_project_before_query(tmp_path):
    q = prepare_run_parameter_query(tmp_path/'bound.cst', 'Schematic:RunID:3', receipt_root=tmp_path)
    code = q['vba_code']
    assert 'names As Variant, values As Variant' in code
    assert 'resolved = GetParameterCombination("Schematic:RunID:3", names, values)' in code
    assert code.index('GetProjectPathName("Project")') < code.index('GetParameterCombination(')
    assert all(word not in code for word in ['GetLastResultID', 'RestoreParameter', 'AddToHistory', '.Update', '.Save', 'CreateObject', 'GetObject'])
    assert not Path(q['output_path']).exists()
    parsed = parse_run_parameter_receipt(wire(q), request=q)
    assert parsed['parameters'] == {'tone':2.5, 'side':1.}
    assert parsed['native_bridge_verified'] is parsed['solver_verified'] is False


@pytest.mark.parametrize('rid', ['Schematic:RunID:0','3D:RunID:3','3',3,True,'Schematic:RunID:3"\nStop'])
def test_only_fixed_positive_schematic_ids_are_allowed(tmp_path, rid):
    with pytest.raises(ValueError):
        prepare_run_parameter_query(tmp_path/'bound.cst', rid, receipt_root=tmp_path)


@pytest.mark.parametrize('issue', ['project','token','rid','truncated','count','duplicate','nan','unresolved'])
def test_wrong_or_incomplete_receipts_are_not_parameters(tmp_path, issue):
    q=prepare_run_parameter_query(tmp_path/'bound.cst','Schematic:RunID:3',receipt_root=tmp_path)
    data=wire(q)
    if issue=='project': data=wire(q,project=tmp_path/'foreign')
    if issue=='token': data=wire(q,token='0'*32)
    if issue=='rid': data=wire(q,rid='Schematic:RunID:4')
    if issue=='truncated': data=data[:data.index('END\t')]
    if issue=='count': data=data.replace('count\t2','count\t3')
    if issue=='duplicate': data=wire(q,rows=[('tone','2'),('TONE','3')])
    if issue=='nan': data=wire(q,rows=[('tone','nan')])
    if issue=='unresolved': data=data.replace('resolved\t1','resolved\t0')
    with pytest.raises(ValueError): parse_run_parameter_receipt(data,request=q)


def test_explicit_project_reader_executes_once_and_never_saves(tmp_path):
    from cst_solver.circuit.native import read_project_run_parameters
    path=tmp_path/'bound.cst'; path.write_bytes(b'unchanged')
    project=SimpleNamespace(filename=lambda:str(path),save=Mock(),close=Mock())
    def execute(code):
        # Transport stub writes the result expected from the generated macro.
        import re
        dest=Path(re.search(r'Open "([^"]+)" For Output',code)[1])
        token=re.search(r'request\t([0-9a-f]{32})',code)[1]
        request={'request_id':token,'project_resources':str(path.with_suffix('')),'result_id':'Schematic:RunID:3'}
        dest.write_text(wire(request),encoding='ascii')
    project.schematic=SimpleNamespace(execute_vba_code=Mock(side_effect=execute))
    out=read_project_run_parameters(project,'Schematic:RunID:3',expected_project_path=path,
                                    receipt_root=tmp_path,confirm_idle=True)
    assert out['parameters']['tone']==2.5
    project.schematic.execute_vba_code.assert_called_once()
    project.save.assert_not_called(); project.close.assert_not_called()
    assert path.read_bytes()==b'unchanged'


@pytest.mark.parametrize('issue',['idle','foreign'])
def test_no_native_call_without_idle_assertion_and_exact_owned_project(tmp_path,issue):
    from cst_solver.circuit.native import read_project_run_parameters
    p=tmp_path/'bound.cst'; project=SimpleNamespace(filename=lambda:str(p),schematic=SimpleNamespace(execute_vba_code=Mock()))
    with pytest.raises(ValueError):
        read_project_run_parameters(project,'Schematic:RunID:3',expected_project_path=p if issue=='idle' else tmp_path/'other.cst',
                                    receipt_root=tmp_path,confirm_idle=issue!='idle')
    project.schematic.execute_vba_code.assert_not_called()


def test_vba_code_unit_hex_preserves_unicode_and_supplementary_names(tmp_path):
    q=prepare_run_parameter_query(tmp_path/'bound.cst','Schematic:RunID:3',receipt_root=tmp_path)
    data=wire(q,rows=[('A','1'), ('\u6e29\u5ea6\U0001f4a1','2.5')])
    assert 'param\t0041\t1' in data
    out=parse_run_parameter_receipt(data,request=q)
    assert out['parameters']=={'A':1., '\u6e29\u5ea6\U0001f4a1':2.5}
