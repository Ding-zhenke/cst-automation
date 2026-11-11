import pytest

from cst_automation.sp_impedance_bridge import build_impedance_query, parse_impedance_receipt


def test_query_is_project_and_task_bound_and_uses_documented_byref(tmp_path):
    p = tmp_path/'model.cst'
    q = build_impedance_query(p, 'SP', ['P1'], receipt_root=tmp_path)
    assert 'GetConstPortImpedance' in q['vba_code']
    assert 'GetPortImpedanceType' in q['vba_code']
    assert q['native_bridge_verified'] is False


def test_parser_rejects_stale_or_inactive_impedance(tmp_path):
    q = build_impedance_query(tmp_path/'model.cst', 'SP', ['P1'], receipt_root=tmp_path)
    encode = lambda s: s.encode('utf-16-be').hex().upper()
    lines = ['CST_SP_IMPEDANCE_V1', 'request\t'+q['request_id'],
             'project\t'+encode(q['project_resources']), 'task\t'+encode('SP'),
             'unit\t'+encode('Ohm'), 'count\t1',
             'port\t'+encode('P1')+'\t'+encode('Constant')+'\t'+encode('None')+'\t'+encode('50')+'\t'+encode('0'),
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
