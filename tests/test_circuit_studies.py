import copy
import json
from pathlib import Path
import pytest
from cst_automation.circuit_studies import normalize_parameter_study
from cst_solver.circuit.study_results import create_archive, store_case, StudyResult


def spec():
    return {'schema_version': 1, 'name': 'filter_scan',
        'parameters': {'load': {'scope': 'circuit', 'unit': 'Ohm', 'block': 'R1', 'property': 'Resistance'}},
        'points': [{'values': {'load': 50}}, {'values': {'load': 75}}],
        'task': {'name': 'AC', 'mode': 'network', 'results': [{'name': 'out', 'tree_path': r'Tasks\AC\Voltages\P', 'run_id': 0}]}}


def curve(unit='V'):
    return {'x': [1., 2.], 'y': [[1., 2.], [3., -4.]], 'x_unit': 'GHz', 'y_unit': unit,
            'tree_path': r'Tasks\AC\Voltages\P', 'run_id': 0, 'domain': 'schematic', 'parameters': {'load': 50}}


def test_normalization_is_independent_and_retains_duplicate_points():
    data=spec(); data['points'][1]=copy.deepcopy(data['points'][0])
    result=normalize_parameter_study(data)
    assert result == data and result is not data
    result['points'][0]['values']['load']=25
    assert data['points'][0]['values']['load']==50


@pytest.mark.parametrize('change', [
    lambda s: s['points'][1]['values'].update(load=float('nan')),
    lambda s: s['points'][1]['values'].clear(),
    lambda s: s['points'][1]['values'].update(extra=1),
    lambda s: s['points'][0]['values'].update(load=True),
    lambda s: s.update(name='../escape'),
    lambda s: s.update(unknown='unsupported'),
    lambda s: s['task']['results'][0].update(run_id=True),
    lambda s: s['task']['results'][0].update(tree_path=r'Tasks\OTHER\V'),
    lambda s: s['task'].update(mode='transient_cosim'),
    lambda s: s['parameters']['load'].update(scope='em'),
    lambda s: s['parameters']['load'].update(unit=''),
])
def test_invalid_plan_fails_pure_preflight(change):
    data=spec(); change(data)
    with pytest.raises(ValueError): normalize_parameter_study(data)


def test_em_parameters_require_em_dependency_and_no_block_binding():
    data=spec(); data['parameters']={'load': {'scope': 'em', 'unit': 'mm'}}
    with pytest.raises(ValueError): normalize_parameter_study(data)
    data['em']={'results': [{'tree_path': r'1D Results\S-Parameters\S1,1', 'run_id': 0}]}
    assert normalize_parameter_study(data)['em'] == data['em']


def archive(tmp_path):
    project=tmp_path/'filter.cst'; project.write_text('fixture')
    return create_archive(project, spec())


def add(batch, cid='p0001', load=50, unit='V', status='succeeded'):
    store_case(batch, {'case_id': cid, 'parameters': {'load': load}, 'status': status,
                      'curves': {'out': curve(unit)}, 'errors': [], 'native_curves': []})


def test_archive_unique_batches_and_immutable_cases(tmp_path):
    batch=archive(tmp_path); add(batch)
    before=(batch/'p0001/case.json').read_bytes()
    with pytest.raises(FileExistsError): add(batch)
    assert (batch/'p0001/case.json').read_bytes()==before
    other=create_archive(tmp_path/'filter.cst', spec())
    assert batch != other
    saved=StudyResult(batch).read_curve('p0001','out')
    assert saved['y']==[1+2j, 3-4j] and saved['run_id']==0
    assert '1.0,1.0,2.0' in (batch/'p0001/out.csv').read_text(encoding='utf-8-sig')


def test_query_filters_parameters_and_compares_components(tmp_path):
    batch=archive(tmp_path); add(batch); add(batch,'p0002',75)
    reader=StudyResult(batch)
    assert [r['case_id'] for r in reader.list_cases({'load': 75})]==['p0002']
    comparison=reader.compare('out',component='magnitude')
    assert len(comparison['curves'])==2
    assert comparison['curves'][0]['y']==pytest.approx([5**.5,5])
    assert reader.compare('out',parameters={'load': 75},component='imag')['curves'][0]['y']==[2,-4]
    with pytest.raises(ValueError): reader.compare('out',component='db')
    with pytest.raises(ValueError): reader.list_cases({'misspelled': 1})
    with pytest.raises(ValueError): reader.read_curve('../escape','out')


def test_unit_mismatch_failed_cases_and_tampering_are_not_silent(tmp_path):
    batch=archive(tmp_path); add(batch); add(batch,'p0002',75,unit='A')
    with pytest.raises(ValueError, match='unit'): StudyResult(batch).compare('out')
    add(batch,'p0003',80,status='failed')
    assert len(StudyResult(batch).list_cases())==3
    assert len(StudyResult(batch).compare('out',parameters={'load': 80})['curves'])==0
    p=batch/'p0001/case.json'; p.write_text(p.read_text()+' ')
    with pytest.raises(ValueError, match='digest'): StudyResult(batch).read_curve('p0001','out')


@pytest.mark.parametrize('wrong', [False,True])
def test_saved_native_readback_compares_samples_and_units(tmp_path,monkeypatch,wrong):
    import cst_solver.circuit.study_results as target
    batch=archive(tmp_path)
    raw=curve();curves=[]
    for component in target.COMPONENTS:
        curves.append({'result_name':'out','component':component,'tree_path':component})
    store_case(batch,{'case_id':'p0001','parameters':{'load':50},'status':'succeeded',
        'curves':{'out':raw},'native_curves':curves})
    def read(path,*,run_id):
        ys,unit=target.component_values({**raw,'y':[1+2j,3-4j]},path)
        if wrong:ys=[99,99]
        return {'x':raw['x'],'y':ys,'x_unit':'GHz','y_unit':unit}
    monkeypatch.setattr(target,'CircuitResult',lambda path:type('R',(),{'read_curve':staticmethod(read)})())
    out=StudyResult(batch).verify_project()
    assert out['saved_readback_verified'] is (not wrong)
    assert out['reopen_verified'] is False
