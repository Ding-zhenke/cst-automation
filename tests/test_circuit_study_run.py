import copy
from pathlib import Path
from types import SimpleNamespace
import pytest
from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError
from cst_solver.circuit.study_results import StudyResult
from test_circuit_studies import spec


class Reader:
    def __init__(self,path): self.path=path
    def read_curve(self,path,*,run_id):
        return {'x':[1.,2.], 'y':[1+2j,3-4j], 'x_unit':'GHz','y_unit':'V',
                'tree_path':path,'run_id':run_id,'parameters':{},'domain':'schematic','sample_digest':'source'}


@pytest.fixture
def rig(tmp_path,monkeypatch):
    import cst_solver.circuit.study as target
    events=[]
    project=tmp_path/'filter.cst';project.write_text('fixture')
    values={}
    def store(name,value):values[name]=float(value);events.append(('parameter',(name,value)))
    s=SimpleNamespace(StoreParameter=store, RestoreDoubleParameter=lambda n:values[n],
        DoesParameterExist=lambda name:True)
    datafile=tmp_path/'em.sig'
    def em_run(**kwargs):
        events.append('em');datafile.write_text(str(events.count('em')))
        return {'status':'succeeded','evidence':{'fresh':True}}
    app=SimpleNamespace(cst_file=SimpleNamespace(filename=lambda:str(project),schematic=s,
        model3d=SimpleNamespace(DoesParameterExist=lambda n:True,RestoreDoubleParameter=lambda n:values[n],
            ResultTree=SimpleNamespace(GetFileFromTreeItem=lambda path:str(datafile)),
            get_solver_run_info=lambda:{'state':'SUCCESS'})),
        save=lambda:events.append('save'),update=lambda:events.append('rebuild'),
        para=lambda *a,**k:store(*a),
        run_checked=em_run)
    api=CircuitAPI(app,adapter=SimpleNamespace())
    api.inspect=lambda:{'parameters':{},'blocks':[{'name':'R1','type':'Resistor'}], 'external_ports':[],
        'nets':[], 'probes':[], 'tasks':[], 'unknown':[]}
    api.set_properties=lambda *a,**k:events.append(('properties',a,k)) or {'readback':a[1]}
    api.run_checked=lambda *a,**k:events.append('circuit') or {'status':'succeeded','saved':True,'run_token':'fresh','errors':[]}
    api.adapter.task=lambda n:{'name':n,'type':'ac','properties':{}}
    def write(s,path,file,x,y,**kwargs):
        Path(file).parent.mkdir(parents=True,exist_ok=True);Path(file).write_text('native')
        events.append(('curve',path,list(y)));return {'tree_path':path,'signal_file':str(file),'points':len(x)}
    class RigReader(Reader):
        def read_curve(self,path,*,run_id):
            return {**super().read_curve(path,run_id=run_id),'parameters':dict(values)}
    monkeypatch.setattr(target,'CircuitResult',RigReader)
    monkeypatch.setattr(target,'write_real_curve',write)
    monkeypatch.setattr(target,'read_em_curve',lambda app,result:RigReader(str(project)).read_curve(result['tree_path'],run_id=result['run_id']))
    return api,events


def test_pure_circuit_keeps_both_cases_and_writes_unique_native_leaves(rig):
    api,events=rig
    out=api.run_parameter_study(spec())
    assert out['status']=='succeeded' and out['reopen_verified'] is False
    rows=StudyResult(out['batch_path']).list_cases()
    assert len(rows)==2 and rows[0]['parameters']=={'load':50}
    paths=[r[1] for r in events if isinstance(r,tuple) and r[0]=='curve']
    assert len(paths)==len(set(paths))==8
    assert events.count('circuit')==2 and 'em' not in events
    data=StudyResult(out['batch_path']).read_curve(rows[0]['case_id'],'out')
    assert data['y']==[1+2j,3-4j]


def em_spec(api):
    old=api.inspect
    api.inspect=lambda:{**old(), "blocks":old()["blocks"]+[{"name":"EM", "type":"CSTMWS", "files":[api.app.cst_file.filename()]}]}
    s=spec(); s['parameters']['length']={'scope':'em','unit':'mm'}
    for i,p in enumerate(s['points']):p['values']['length']=i+1.
    s['em']={'results':[{'tree_path':r'1D Results\S-Parameters\S1,1','run_id':0}]}
    return s


def test_em_rebuild_precedes_every_circuit_and_source_is_retained(rig):
    api,events=rig
    out=api.run_parameter_study(em_spec(api))
    assert out['status']=='succeeded'
    stages=[e for e in events if isinstance(e,str) and e in ['rebuild','em','circuit']]
    assert stages==['rebuild','em','circuit','rebuild','em','circuit']
    reader=StudyResult(out['batch_path']);row=reader.list_cases()[0]
    case=reader.case(row['case_id'])
    assert case['em']['results'][0]['run_id']==0
    assert case['em']['reused'] is False


def test_whole_plan_preflight_happens_before_first_write(rig):
    api,events=rig
    s=spec();s['points'][1]['values']['load']=float('nan')
    with pytest.raises((ValueError,CircuitError)): api.run_parameter_study(s)
    assert events==[]


def test_unknown_block_and_global_parameter_fail_before_write(rig):
    api,events=rig
    s=spec();s['parameters']['load']['block']='Missing'
    with pytest.raises(CircuitError):api.run_parameter_study(s)
    s=spec();s['parameters']['load'].pop('block');s['parameters']['load'].pop('property')
    api.app.cst_file.schematic.DoesParameterExist=lambda n:False
    with pytest.raises(CircuitError):api.run_parameter_study(s)
    assert events==[]


@pytest.mark.parametrize('stage',['em','circuit'])
def test_unverified_stage_stops_and_retains_failure_record(rig,stage):
    api,events=rig
    if stage=='em':api.app.run_checked=lambda **k:{'status':'unverified'}
    else:api.run_checked=lambda *a,**k:{'status':'unverified','errors':[]}
    out=api.run_parameter_study(em_spec(api))
    assert out['status']=='unverified'
    rows=StudyResult(out['batch_path']).list_cases()
    assert len(rows)==1 and rows[0]['status']=='unverified'
    if stage=='em':assert 'circuit' not in events


def test_duplicate_points_and_rerun_never_overwrite(rig):
    api,events=rig
    s=spec();s['points'][1]=copy.deepcopy(s['points'][0])
    first=api.run_parameter_study(s); second=api.run_parameter_study(s)
    assert first['batch_path'] != second['batch_path']
    rows=StudyResult(first['batch_path']).list_cases()
    assert rows[0]['case_id']!=rows[1]['case_id']


def test_curve_write_failure_preserves_raw_complex_data(rig,monkeypatch):
    api,events=rig
    import cst_solver.circuit.study as target
    monkeypatch.setattr(target,'write_real_curve',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('write stopped')))
    out=api.run_parameter_study(spec())
    assert out['status']=='failed'
    reader=StudyResult(out['batch_path']); row=reader.list_cases()[0]
    assert reader.read_curve(row['case_id'],'out')['y']==[1+2j,3-4j]


def test_parameter_readback_must_match_before_circuit_execution(rig):
    api,events=rig
    api.set_properties=lambda *a,**k:{'readback':{'Resistance':'999'},'resolved_si':{'blocks':{'R1':{'Resistance':50}}}}
    out=api.run_parameter_study(spec())
    assert out['status']=='unverified'
    assert 'circuit' not in events


def test_raw_snapshot_exists_before_native_tree_mutation(rig,monkeypatch):
    api,events=rig
    import cst_solver.circuit.study as target
    old=target.write_real_curve
    def write(*args,**kwargs):
        root=Path(api.app.cst_file.filename()).with_suffix('')/'Result/DS/Studies'
        assert list(root.rglob('p0001.sources.json'))
        return old(*args,**kwargs)
    monkeypatch.setattr(target,'write_real_curve',write)
    assert api.run_parameter_study(spec())['status']=='succeeded'


def test_execution_rejects_historical_source_alias_before_writes(rig):
    api,events=rig
    data=spec();data['task']['results'][0]['run_id']=7
    with pytest.raises(CircuitError):api.run_parameter_study(data)
    assert events==[]



def test_em_log_only_success_cannot_release_circuit(rig,monkeypatch):
    api,events=rig
    import cst_solver.circuit.study as target
    monkeypatch.setattr(target,'em_result_probe',lambda app,results:{'items':[{'tree_path':'EM','exists':True,'mtime_ns':1,'sha256':'unchanged'}]})
    out=api.run_parameter_study(em_spec(api))
    assert out['status']=='unverified' and 'circuit' not in events


def test_em_probe_tracks_only_requested_native_data_file(tmp_path):
    from cst_solver.circuit.study import em_result_probe
    project=tmp_path/'p.cst';project.write_text('fixture')
    result=tmp_path/'data.sig';result.write_text('same result')
    app=SimpleNamespace(cst_file=SimpleNamespace(filename=lambda:str(project),
        model3d=SimpleNamespace(ResultTree=SimpleNamespace(GetFileFromTreeItem=lambda path:str(result)))))
    requests=[{'tree_path':r'1D Results\S-Parameters\S1,1','run_id':0}]
    before=em_result_probe(app,requests)
    (tmp_path/'Model.log').write_text('new solver log')
    assert em_result_probe(app,requests)==before
    result.write_text('new result data')
    assert em_result_probe(app,requests)!=before


def test_source_global_parameter_mismatch_is_not_archived_as_success(rig,monkeypatch):
    api,events=rig
    import cst_solver.circuit.study as target
    data=spec(); data['parameters']['load'].pop('block');data['parameters']['load'].pop('property')
    class Wrong(Reader):
        def read_curve(self,path,*,run_id):
            return {**super().read_curve(path,run_id=run_id),'parameters':{'load':999}}
    monkeypatch.setattr(target,'CircuitResult',Wrong)
    out=api.run_parameter_study(data)
    assert out['status']=='unverified'
    assert not any(isinstance(e,tuple) and e[0]=='curve' for e in events)


def test_em_parameter_mismatch_cannot_release_circuit(rig,monkeypatch):
    api,events=rig
    import cst_solver.circuit.study as target
    monkeypatch.setattr(target,'read_em_curve',lambda app,result:{**Reader('').read_curve(result['tree_path'],run_id=0),
        'domain':'3d','parameters':{'length':999}})
    out=api.run_parameter_study(em_spec(api))
    assert out['status']=='unverified' and 'circuit' not in events



def test_later_illegal_model_selector_is_rejected_before_any_write(rig):
    api,events=rig
    old=api.inspect
    api.inspect=lambda:{**old(),'blocks':old()['blocks']+[{'name':'D1','type':'Diode'}]}
    data=spec();data['parameters']['model']={'scope':'circuit','unit':'1','block':'D1','property':'Model Type'}
    for point in data['points']:point['values']['model']=2
    with pytest.raises(CircuitError):api.run_parameter_study(data)
    assert events==[]


@pytest.mark.parametrize('parameters', [{},{'load':'50'},{'load':'999'}])
def test_source_global_parameters_require_numeric_matching_values(rig,monkeypatch,parameters):
    api,events=rig
    import cst_solver.circuit.study as target
    data=spec();data['points']=data['points'][:1]
    data['parameters']['load'].pop('block');data['parameters']['load'].pop('property')
    class Actual(Reader):
        def read_curve(self,path,*,run_id):
            return {**super().read_curve(path,run_id=run_id),'parameters':parameters}
    monkeypatch.setattr(target,'CircuitResult',Actual)
    out=api.run_parameter_study(data)
    assert out['status']==('succeeded' if parameters=={'load':'50'} else 'unverified')



def test_incomplete_em_solver_cannot_release_circuit_even_with_new_files(rig):
    api,events=rig
    api.app.cst_file.model3d.get_solver_run_info=lambda:{'state':'RUNNING'}
    out=api.run_parameter_study(em_spec(api))
    assert out['status']=='unverified' and 'circuit' not in events


def test_identical_em_points_are_allowed_with_new_native_file_evidence(rig):
    api,events=rig
    data=em_spec(api);data['points'][1]=copy.deepcopy(data['points'][0])
    out=api.run_parameter_study(data)
    assert out['status']=='succeeded' and events.count('em')==events.count('circuit')==2
