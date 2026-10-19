from types import SimpleNamespace
import copy

import pytest

from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError, NativeAdapter
from cst_solver.circuit.capabilities import circuit_capabilities


def test_environment_pid_accepts_cst_method_and_property_forms():
    from cst_solver.environment import environment_pid
    assert environment_pid(SimpleNamespace(pid=lambda: 1234)) == 1234
    assert environment_pid(SimpleNamespace(pid=5678)) == 5678
    assert environment_pid(SimpleNamespace(pid=lambda: None)) is None


def test_intrinsic_block_without_file_does_not_query_unsupported_file_count():
    from cst_solver.circuit.adapter import block_files
    obj = SimpleNamespace(GetFile=lambda: "", GetNumberOfFiles=lambda: pytest.fail("Not supported for intrinsic resistor"))
    assert block_files(obj, "Resistor") == []


class Adapter:
    """In-memory external boundary, not an EM/circuit solver."""
    def __init__(self):
        self.snapshot = {"blocks": [], "external_ports": [], "nets": [], "probes": [], "tasks": [], "units": {}, "parameters": {}, "unknown": []}
        self.updated = []
        self.proof = {}
        self.fail_write = False

    def inspect(self): return copy.deepcopy(self.snapshot)
    def apply(self, spec):
        if self.fail_write: raise RuntimeError("native write interrupted")
        for key in self.snapshot:
            if key in spec: self.snapshot[key] = copy.deepcopy(spec[key])
        for block in self.snapshot["blocks"]:
            block["pins"] = [{"pin_name": "1", "port_index": 7}, {"pin_name": "2", "port_index": 9}]
    def task(self, name):
        return next(t for t in self.snapshot["tasks"] if t["name"] == name)
    def update_task(self, name): self.updated.append(name)
    def execution_evidence(self, task, token): return dict(self.proof)
    def properties(self, name, props, units):
        b = next(b for b in self.snapshot["blocks"] if b["name"] == name)
        b["properties"].update(props)
    def dependencies(self): return {"files": [], "unknown": [], "complete": True}
    def link_em(self, **kwargs): return dict(kwargs, verified=False, reason="EM port readback pending")


def raw_spec():
    return {"schema_version": 1, "units": {}, "parameters": {}, "blocks": [], "external_ports": [],
            "nets": [], "probes": [], "em_links": [],
            "tasks": [{"name": "T", "type": "transient", "properties": {"circuit simulator": "cosimulation"}}]}


@pytest.fixture
def env(tmp_path):
    path = tmp_path / "sample.cst"
    path.write_text("offline project", encoding="utf-8")
    saves = []
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: str(path)),
                          save=lambda *args, **kwargs: saves.append(str(path)) or str(path),
                          get_messages=lambda: [])
    adapter = Adapter()
    api = CircuitAPI(app, adapter=adapter)
    return api, adapter, saves


def test_static_discovery_does_not_claim_license_or_live_validation():
    caps = circuit_capabilities()
    assert caps["license"] == "unknown"
    assert caps["verification"]["transient_cosim"] == "not_run"
    with pytest.raises(CircuitError): circuit_capabilities(probe="live")


def test_conflict_does_not_delete_existing_object(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    with pytest.raises(CircuitError, match="conflict"):
        api.apply(raw_spec())
    assert [t["name"] for t in adapter.snapshot["tasks"]] == ["T"]


def test_partial_write_is_explicit_and_preserves_phase(env):
    api, adapter, _ = env
    adapter.fail_write = True
    with pytest.raises(CircuitError) as error: api.apply(raw_spec())
    assert error.value.code == "circuit_build_partial"
    assert error.value.details["stage"] == "apply"


def test_run_rejects_wrong_mode_before_submission(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="network", expected_results=[{"tree_path": "T\\Voltages\\V1", "run_id": 4}])
    assert result["status"] == "failed"
    assert adapter.updated == []


def test_update_selected_task_and_missing_evidence_is_unverified(env):
    api, adapter, saves = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "T\\Voltages\\V1", "run_id": 4}])
    assert adapter.updated == ["T"]
    assert saves
    assert result["status"] == "unverified"
    assert result["run_token"]
    assert result["errors"][0]["code"] == "circuit_result_unverified"
    assert result["audit_path"]


def test_rejects_results_belonging_to_another_task_before_run(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "Other\\Voltage", "run_id": 0}])
    assert result["status"] == "failed" and adapter.updated == []


def test_verified_cache_not_assumed_from_unchanged_results(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="transient_cosim", reuse="verified", expected_results=[{"tree_path": "T\\V", "run_id": 1}])
    assert result["status"] == "unverified"
    assert adapter.updated == []


def test_native_index_lookup_uses_port_name_without_subtraction():
    block = SimpleNamespace(Reset=lambda: None, Name=lambda name: None, GetPortIndex=lambda name: {"sig": 7, "ref": 11}[name])
    native = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=block))))
    assert native.endpoint(["Block", "B", "ref"]) == ["Block", "B", 11]


def test_schematic_none_is_explicit():
    with pytest.raises(CircuitError) as error:
        NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=None)))
    assert error.value.code == "circuit_unavailable"


def test_setup_circuit_property_is_lazy():
    from cst_solver import setup
    app = setup.__new__(setup)
    app.cst_file = None
    assert isinstance(app.circuit, CircuitAPI)
    with pytest.raises(CircuitError): app.circuit.inspect()


def test_target_completion_without_matching_result_run_is_unverified(env, monkeypatch):
    api, adapter, _ = env
    api.apply(raw_spec())
    adapter.execution_evidence = lambda name, token: {"completed": True, "em_completed": True, "task_name": name, "run_token": token, "mode": "transient_cosim",
                                                     "circuit_runs": [{"tree_path": "T\\V", "run_id": 8}]}
    import cst_solver.circuit.results as results
    monkeypatch.setattr(results, "CircuitResult", lambda path: SimpleNamespace(read_curve=lambda *a, **k: {"parameters": {}, "run_id": 7}))
    out = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "T\\V", "run_id": 7}])
    assert out["status"] == "unverified"


def test_native_properties_use_si_local_units_without_changing_existing_global_units():
    stored, units = {}, {}
    obj = SimpleNamespace(Reset=lambda: None, Name=lambda n: None, GetTypeName=lambda: 'Capacitor', SetLocalUnitForProperty=lambda k,u: units.update({k:u}),
                          SetDoubleProperty=lambda k,v: stored.update({k:v}), GetProperty=lambda k: stored[k])
    native = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=obj, Units=SimpleNamespace(SetUnit=lambda *a: pytest.fail("Existing global units must not change"))))))
    native.properties("C1", {"Capacitance": "2*Cval"}, {"Capacitance": "pF"}, {"Cval": {"value": 1, "unit": "pF"}})
    assert float(stored["Capacitance"]) == pytest.approx(2e-12)
    assert units["Capacitance"] == "F"


def test_incomplete_dependency_closure_prevents_submission(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    adapter.dependencies = lambda: {"files": [], "unknown": [{"reason": "cycle"}], "complete": False}
    result = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "T\\V", "run_id": 4}])
    assert result["status"] != "succeeded" and adapter.updated == []


def test_external_model_changed_during_execution_cannot_be_accepted(env):
    api, adapter, _ = env
    raw = raw_spec()
    raw['tasks'][0]['type'] = 's-parameters'
    raw['external_ports'] = [{'name': '1'}]
    api.apply(raw)
    version = {'sha': 'before'}
    adapter.dependencies = lambda: {'files': [{'path': 'model.cir', 'exists': True, 'sha256': version['sha']}], 'unknown': [], 'complete': True}
    def execute(name):
        adapter.updated.append(name)
        version['sha'] = 'after'
    adapter.update_task = execute
    adapter.execution_evidence = lambda name, token: {'completed': True, 'task_name': name, 'run_token': token, 'mode': 'network', 'circuit_runs': [{'tree_path': 'T\\V', 'run_id': 0}]}
    result = api.run_checked('T', mode='network', expected_results=[{'tree_path': 'T\\V', 'run_id': 0}])
    assert result['status'] == 'unverified'
    assert result['execution_evidence']['external_dependencies_unchanged'] is False


def test_existing_and_unreadable_parameters_are_not_overwritten(env):
    api, adapter, _ = env
    raw = raw_spec()
    raw["parameters"] = {"Cval": {"value": 1, "unit": "pF"}}
    adapter.snapshot["parameters"] = {"Cval": "original"}
    with pytest.raises(CircuitError): api.apply(raw)
    assert adapter.snapshot["parameters"]["Cval"] == "original"
    adapter.snapshot["parameters"] = None
    with pytest.raises(CircuitError): api.apply(raw)


def test_run_without_saved_project_returns_structured_failure():
    api = CircuitAPI(SimpleNamespace(cst_file=None))
    out = api.run_checked("T", mode="network", expected_results=[{"tree_path": "T\\V", "run_id": 1}])
    assert out["status"] == "failed" and out["errors"][0]["code"] == "circuit_unavailable"

def test_native_new_net_uses_generated_name_before_explicit_rename():
    from cst_solver.circuit.adapter import create_net
    calls=[]
    obj=SimpleNamespace(Reset=lambda: calls.append('reset'),
        AddComponentPorts=lambda name, eps, label: calls.append(('add', name, eps, label)) or 'net1',
        Rename=lambda old,new: calls.append(('rename',old,new)), Apply=lambda: calls.append('apply'))
    create_net(obj,'input',[['Block','R1',0],['ExternalPort','1',0]])
    assert calls[1][1] == ''
    assert calls[2:] == [('rename','net1','input'),'apply']

def test_native_task_type_is_normalized_from_actual_cst_readback():
    obj=SimpleNamespace(Reset=lambda:None,Name=lambda n:None,DoesExist=lambda:True,GetTypeForTask=lambda n:'Transient',GetProperty=lambda n:'cosimulation')
    native=NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(SimulationTask=obj))))
    assert native.task('T') == {'name':'T','type':'transient','properties':{'circuit simulator':'cosimulation'}}

def test_info_messages_do_not_reject_verified_target_execution(env,monkeypatch):
    api,adapter,_=env
    api.apply(raw_spec())
    api.app.get_messages=lambda:[{'type':'INFO','text':'Task T successfully completed.'}]
    adapter.execution_evidence=lambda name,token:{'completed':True,'em_completed':True,'task_name':name,'run_token':token,'mode':'transient_cosim','circuit_runs':[{'tree_path':'Tasks\\T\\V','run_id':0}],'em_runs':[{'domain':'3d','run_id':1}]}
    import cst_solver.circuit.results as results
    monkeypatch.setattr(results,'CircuitResult',lambda path:SimpleNamespace(read_curve=lambda *a,**k:{'parameters':{},'run_id':0}))
    result=api.run_checked('T',mode='transient_cosim',expected_results=[{'tree_path':'Tasks\\T\\V','run_id':0}])
    assert result['status']=='succeeded'
    assert result['messages'][0]['type']=='INFO'


def test_native_log_requires_fresh_target_completion():
    from cst_solver.circuit.evidence import log_completion
    log='2026-10-19 Task: SP\nTolerance Settings\nTask time: 0 sec\nTotal time: 0 sec\n'
    assert log_completion('old',log,'SP')['completed']
    for before,after,name in [(log,log,'SP'),('old',log,'Other'),('old',log+'ERROR: invalid model','SP'),('old','Task: SP\n','SP')]:
        assert not log_completion(before,after,name)['completed']

def test_tolerance_error_current_is_not_a_solver_error():
    from cst_solver.circuit.evidence import log_completion
    assert log_completion('', 'Task: SP\nRelative tolerance on error current: 1e-06\nTask time: 0 sec\nTotal time: 0 sec','SP')['completed']

def test_self_link_accepts_actual_cst_2026_schematic_block_type():
    native=NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace())))
    native.inspect=lambda:{'blocks':[{'name':'MWSSCHEM1','type':'CST MICROWAVE STUDIO schematic block'}]}
    native.pins=lambda name:[{'pin_name':'1','port_index':0}]
    out=native.link_em(block_name='MWSSCHEM1',source='self',port_map=[{'pin_name':'1'}],parameter_map={})
    assert out['block_name']=='MWSSCHEM1' and out['verified'] is False

def test_old_completion_cannot_be_reused_by_unrelated_log_append():
 from cst_solver.circuit.evidence import log_completion
 old='Task: SP\nTask time: 0 sec\nTotal time: 0 sec\n'
 assert not log_completion(old,old+'Starting new update...\n','SP')['completed']
 assert not log_completion('header1\n'+old,'header2\n'+old,'SP')['completed']
 assert log_completion(old,old+'Task: SP\nTask time: 1 sec\nTotal time: 1 sec\n','SP')['completed']


def test_unknown_input_readback_cannot_prove_unchanged():
 from cst_solver.circuit.evidence import configuration_complete
 assert configuration_complete({'unknown':[{'field':'parameter_dimensions','status':'unknown'}]})
 assert not configuration_complete({'unknown':[{'field':'C1.Capacitance','error':'not readable'}]})

def test_cosim_em_log_needs_new_completion_and_matching_task():
 from cst_solver.circuit.evidence import em_log_completion
 before='2026-10-19 10:00 Solver started at: old\nNetwork co-simulation\nSolver finished at: old\n'
 after='2026-10-19 10:01 Solver started at: new\nNetwork co-simulation\nSolver finished at: new\n'
 output='Network co-simulation: Task TR\nMaximum simulation time reached, solver stopped.'
 assert em_log_completion(before,after,output,'TR','SUCCESS')['em_completed']
 assert not em_log_completion(before,before,output,'TR','SUCCESS')['em_completed']
 assert not em_log_completion(before,after,output,'Other','SUCCESS')['em_completed']
 assert not em_log_completion(before,after,output,'TR','RUNNING')['em_completed']
 assert not em_log_completion(before,after,output+'\nERROR: failed','TR','SUCCESS')['em_completed']

def test_cosim_cannot_reuse_old_task_output_for_another_em_run():
 from cst_solver.circuit.evidence import em_log_completion
 old='Solver started at: old\nNetwork co-simulation\nSolver finished at: old\n'
 after=old+'Solver started at: new\nUnrelated ordinary solver\nSolver finished at: new\n'
 output='Network co-simulation: Task TR\nMaximum simulation time reached, solver stopped.'
 assert not em_log_completion(old,after,output,'TR','SUCCESS',output_before=output)['em_completed']


def test_em_time_coverage_does_not_expand_with_sparse_data():
 from cst_solver.circuit.evidence import time_coverage
 assert not time_coverage([0.,20e-9],40e-9)
 assert not time_coverage([i*5e-12 for i in range(4001)],40e-9)
 assert time_coverage([i*5e-12 for i in range(8001)],40e-9)

def test_diode_legacy_alias_maps_to_documented_native_type():
 from cst_solver.circuit.adapter import native_block_type
 assert native_block_type(r'CircuitSemiconductor\Diode') == r'CircuitSemi\Diode'
 assert native_block_type(r'CircuitBasic\Resistor') == r'CircuitBasic\Resistor'

def test_native_execution_never_attributes_historical_run_ids(tmp_path,monkeypatch):
    path=tmp_path/'saved.cst';path.write_text('offline fixture')
    log=path.with_suffix('')/'Result/DS/Model.log';log.parent.mkdir(parents=True)
    log.write_text('Task: SP\nTask time: 0 sec\nTotal time: 0 sec\n')
    app=SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(),filename=lambda:str(path)))
    native=NativeAdapter(app);snapshot={'unknown':[]}
    native.inspect=lambda:snapshot;native.task=lambda name:{'name':name,'type':'s-parameters','properties':{}}
    native._last_update={'returned':True,'task_name':'SP','path':str(path),'log_path':str(log),'log_before':'old','configuration':snapshot,'prior_messages':[]}
    import cst_solver.circuit.results as results
    monkeypatch.setattr(results,'CircuitResult',lambda path:SimpleNamespace(get_tree_items=lambda **kw:['Tasks\\SP\\S-Parameters\\S2,1'],get_run_ids=lambda p:[7,9]))
    out=native.execution_evidence('SP','offline-test-token')
    assert not out['completed'] and out['circuit_runs']==[]
