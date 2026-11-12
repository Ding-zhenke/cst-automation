import pytest

from cst_automation.sp_impedance_bridge import build_impedance_query, parse_impedance_receipt


def test_query_is_project_and_task_bound_and_uses_documented_byref(tmp_path):
    p = tmp_path/'model.cst'
    q = build_impedance_query(p, 'SP', ['P1'], receipt_root=tmp_path)
    assert 'GetConstPortImpedance' in q['vba_code']
    assert 'GetPortImpedanceType' in q['vba_code']
    assert 'GetPortSourceType' not in q['vba_code']
    assert q['native_bridge_verified'] is False


def test_parser_rejects_stale_or_inactive_impedance(tmp_path):
    q = build_impedance_query(tmp_path/'model.cst', 'SP', ['P1'], receipt_root=tmp_path)
    encode = lambda s: s.encode('utf-16-be').hex().upper()
    lines = ['CST_SP_IMPEDANCE_V1', 'request\t'+q['request_id'],
             'project\t'+encode(q['project_resources']), 'task\t'+encode('SP'),
             'unit\t'+encode('Ohm'), 'count\t1',
             'port\t'+encode('P1')+'\t'+encode('Constant')+'\t'+encode('unsupported')+'\t'+encode('50')+'\t'+encode('0'),
             'END\t'+q['request_id']]
    parsed = parse_impedance_receipt('\n'.join(lines), request=q)
    assert parsed['ports']['P1']['real'] == 50 and parsed['native_bridge_verified'] is False
    assert parsed['schematic_identity_verified'] is False
    with pytest.raises(ValueError): parse_impedance_receipt('\n'.join(lines).replace('Constant'.encode('utf-16-be').hex().upper(), encode('Block_Dependent')), request=q)
    with pytest.raises(ValueError): parse_impedance_receipt('\n'.join(lines[:-1]), request=q)
    wrong_project = list(lines); wrong_project[2] = 'project\t'+encode(str(tmp_path/'other'))
    with pytest.raises(ValueError): parse_impedance_receipt('\n'.join(wrong_project), request=q)
    comma = list(lines); comma[6] = comma[6].replace(encode('50'), encode('50,5'))
    with pytest.raises(ValueError): parse_impedance_receipt('\n'.join(comma), request=q)


def test_owned_byref_execution_parses_bound_receipt_without_saving(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from cst_solver.circuit.native import read_project_sp_impedances
    from cst_solver import native
    project_path = tmp_path/'model.cst'; audit = tmp_path/'audit'
    project = SimpleNamespace(filename=lambda: str(project_path))
    calls = []
    def execute(project_arg, code, *, target):
        calls.append((project_arg, target))
        manifest = next(audit.glob('*.request.json'))
        q = json.loads(manifest.read_text(encoding='utf-8'))
        encode = lambda s: s.encode('utf-16-be').hex().upper()
        lines = ['CST_SP_IMPEDANCE_V1', 'request\t'+q['request_id'],
                 'project\t'+encode(q['project_resources']), 'task\t'+encode('SP'),
                 'unit\t'+encode('Ohm'), 'count\t1',
                 'port\t'+encode('P1')+'\t'+encode('Constant')+'\t'+encode('unsupported')+'\t'+encode('75')+'\t'+encode('0'),
                 'END\t'+q['request_id']]
        from pathlib import Path
        Path(q['output_path']).write_text('\n'.join(lines), encoding='ascii')
    monkeypatch.setattr(native, 'execute_vba', execute)
    report = read_project_sp_impedances(project, 'SP', ['P1'], expected_project_path=str(project_path),
                                        receipt_root=audit, confirm_idle=True)
    assert calls == [(project, 'schematic')]
    assert report['ports']['P1']['real'] == 75
    assert report['native_bridge_verified'] is False and report['idle_verified'] is False


def test_owned_byref_rejects_wrong_path_before_native(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from cst_solver.circuit.native import read_project_sp_impedances
    from cst_solver import native
    monkeypatch.setattr(native, 'execute_vba', lambda *a, **kw: pytest.fail('No native call'))
    with pytest.raises(ValueError):
        read_project_sp_impedances(SimpleNamespace(filename=lambda: str(tmp_path/'other.cst')),
            'SP', ['P1'], expected_project_path=str(tmp_path/'model.cst'), receipt_root=tmp_path, confirm_idle=True)
