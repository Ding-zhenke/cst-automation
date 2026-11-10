"""Synthetic native boundary: no CST process, project controller or solver."""
from pathlib import Path
from types import SimpleNamespace
import copy

import numpy as np
import pytest

from cst_automation import embedded_network as data
from cst_solver.circuit import embedded_network as native
from tpc_service.sessions import embedded_network as service
from tpc_service.sessions.store import read, write
from tpc_service.errors import ServiceError
from test_workflow_enforcement import setup, submit, prepare_em_evidence, hb, native_app


def sample(root, n=3):
    f = np.array([2e6, 4e6, 8e6, 20e6])
    a = np.diag(-np.arange(1, n+1)*1e8)
    b = np.eye(n)*1e7
    c = np.eye(n)
    d = np.eye(n)*.1
    s = np.asarray([d+c@np.linalg.solve(2j*np.pi*v*np.eye(n)-a, b) for v in f])
    path = root/'matrix.npz'
    ports = list(range(2, 2*n+1, 2))
    np.savez(path, frequency_hz=f, S=s, ports=ports)
    p = dict(project_id='p', em_job_id='em', run_id=3, matrix_path=str(path), matrix_sha256=data.digest(path),
        physical_port_ids=ports, native_reference_ohms=[75]*n, reference_ohm=75,
        low_frequencies_hz=f[:3].tolist(), frequency_atol_hz=.01,
        block_name='Existing', expected_payload_sha256='0'*64, output_path=str(root/f'new.s{n}p'),
        settings=dict(accuracy_abs=1e-5, maximum_poles=30, enhance_dc=True, passivate=True),
        limits=dict(fit_max_error=.001, dc_solve_residual=1e-10, dc_max_singular=1.00001,
                    dc_reciprocity_error=.001, roundtrip_error=1e-12, native_matrix_error=1e-10, native_sample_residual=1e-6))
    return p, f, s, (a, b, c, d)


def exports(paths, matrices, ref=75, error=1e-8):
    for k, m in zip('ABCD', matrices):
        path = Path(paths[k]); path.parent.mkdir(parents=True, exist_ok=True)
        np.savetxt(path, m, delimiter=',')
    n = matrices[3].shape[0]
    Path(paths['log']).write_text('State space formulation has been successfully generated.\n'
        'dx/dt = [A] * x + [B] * u\ny     = [C] * x + [D] * u\n'
        f'dim(x) = {len(matrices[0])}\ndim(u) = {n}\ndim(y) = {n}\nScattering formulation\n'
        'Reference impedances:\n'+''.join(f'Port {i}: {ref} Ohm\n' for i in range(1, n+1))+
        'Port labels:\n'+''.join(f'Port {i}: "{i}"\n' for i in range(1, n+1))+
        f'Achieved accuracy in vector fitting of S-Parameters: {error}\n')


@pytest.mark.parametrize('n', [1, 2, 3])
def test_touchstone_roundtrip_preserves_asymmetric_order(tmp_path, n):
    s = (np.arange(2*n*n).reshape(2, n, n)+1j)/100
    path = tmp_path/f's.s{n}p'
    data.write_touchstone(path, [0, 4e6], s, 75)
    f, got = data.read_touchstone(path, n, 75)
    assert np.array_equal(f, [0, 4e6]) and np.array_equal(got, s)
    if n == 2:
        numbers = [float(v) for v in path.read_text().splitlines()[1].split()]
        assert numbers[3:5] == [s[0, 1, 0].real, s[0, 1, 0].imag]


def test_renormalization_matches_independent_impedance_formula():
    s = np.array([[[.1+.02j, .2-.01j], [.07+.03j, -.1+.01j]]])
    refs = np.array([40, 110]); q = np.diag(np.sqrt(refs)); eye = np.eye(2)
    z = q@(eye+s[0])@np.linalg.inv(eye-s[0])@q
    expected = (z-75*eye)@np.linalg.inv(z+75*eye)
    assert np.max(abs(data.renormalize(s, refs, 75)[0]-expected)) < 1e-14


@pytest.mark.parametrize('bad', ['sha', 'ports', 'nan', 'grid', 'missing_lf', 'object', 'extra'])
def test_source_invalid_before_native(tmp_path, bad):
    p, f, s, _ = sample(tmp_path)
    if bad == 'sha': p['matrix_sha256'] = 'f'*64
    elif bad == 'ports': p['physical_port_ids'].reverse()
    elif bad == 'missing_lf': p['low_frequencies_hz'][0] += 100
    else:
        if bad == 'nan': s[0, 0, 0] = np.nan
        if bad == 'grid': f[1] = f[0]
        if bad == 'object': s = s.astype(object)
        extra = {'other': 1} if bad == 'extra' else {}
        np.savez(p['matrix_path'], frequency_hz=f, S=s, ports=p['physical_port_ids'], **extra)
        p['matrix_sha256'] = data.digest(p['matrix_path'])
    with pytest.raises(ValueError): data.load_matrix(p)


class FakeBlock:
    def __init__(self, adapter): self.adapter = adapter; self.name = ''; self.pending = {}; self.values = {}
    def Reset(self): self.pending = {}
    def Name(self, name): self.name = name
    def Type(self, kind): self.pending['type'] = kind
    def Position(self, x, y): self.pending['position'] = (x, y)
    def DoesExist(self): return self.name in self.adapter.blocks
    def GetTypeName(self): return self.adapter.blocks[self.name]['type']
    def GetNumberOfFiles(self): return 1
    def GetNumberOfPorts(self): return len(self.adapter.p['physical_port_ids'])
    def GetPortName(self, i): return str(i+1)
    def GetFile(self): return self.adapter.blocks[self.name]['file']
    def IsCachingFiles(self): pytest.fail('Embedded blocks do not support this getter')
    def SetFile(self, path):
        if self.DoesExist():
            self.adapter.writes.append((self.name, path))
            self.adapter.blocks[self.name]['file'] = path
        else: self.pending['file'] = path
    def Create(self):
        self.adapter.creates += 1
        self.adapter.blocks[self.name] = dict(type='TOUCHSTONE block', file=self.pending['file'])
        if self.adapter.failure == 'create_nets': self.adapter.nets = []
    def Delete(self):
        assert self.name != 'Existing'
        del self.adapter.blocks[self.name]
        if self.adapter.failure == 'nets': self.adapter.nets = []
    def CanUseMOR(self): return True
    def ExtractStateSpaceModel(self, *args):
        assert args == ('', '')
        _, paths, _ = native.paths(self.adapter.project, self.adapter.p['output_path'], 'job')
        exports(paths, self.adapter.matrices, error=.1 if self.adapter.failure == 'fit' else 1e-8)
    def __getattr__(self, name):
        if name.startswith('Set'):
            return lambda value: self.values.__setitem__(name[3:], value)
        if name.startswith('Get'):
            return lambda: ('Built-in' if name == 'GetVectorFittingMethod' else self.values[name[3:]])
        raise AttributeError(name)


class Adapter:
    def __init__(self, root, p, matrices, failure=None):
        self.p = p; self.matrices = matrices; self.failure = failure
        self.project = root/'model.cst'; self.project.write_text('synthetic')
        self.payload = self.project.with_suffix('')/'Model'/'DS'/'Block'/'0'/'old.s3p'
        self.payload.parent.mkdir(parents=True); self.payload.write_text('old payload')
        p['expected_payload_sha256'] = data.digest(self.payload)
        self.blocks = {'Existing': dict(type='TOUCHSTONE block', file=str(self.payload))}
        self.writes = []; self.creates = 0; self.nets = [{'name': 'wire', 'subnets': [[['Block', 'Existing', 0]]]}]
        self.schematic = SimpleNamespace(Block=FakeBlock(self), Units=SimpleNamespace(GetUnit=lambda _: 'MHz'))
    def select(self, kind, name):
        b = self.schematic.Block; b.Reset(); b.Name(name); return b
    def pins(self, name):
        return [dict(pin_name=str(i+1), port_index=i, pin_index=i) for i in range(len(self.p['physical_port_ids']))]
    def inspect(self):
        return dict(blocks=[dict(name=k, type=v['type'], pins=self.pins(k), files=[v['file']]) for k, v in self.blocks.items()],
                    external_ports=[], nets=copy.deepcopy(self.nets), probes=[], tasks=[dict(name='HB', type='spectral lines')],
                    units={'Frequency': 'MHz'}, parameters={}, unknown=[{'field': 'parameter_dimensions'}])
    def save(self):
        source = Path(self.blocks['Existing']['file'])
        self.payload.write_bytes(b'wrong' if self.failure == 'saved' else source.read_bytes())
        self.blocks['Existing']['file'] = str(self.payload)


def fixture_native(tmp_path, failure=None):
    p, f, s, matrices = sample(tmp_path)
    adapter = Adapter(tmp_path, p, matrices, failure)
    app = native_app(); app.circuit.adapter = adapter
    return p, adapter, app


def test_embedded_native_success_keeps_target_and_checks_saved_payload(tmp_path):
    p, adapter, app = fixture_native(tmp_path)
    before = copy.deepcopy(adapter.nets)
    receipt = native.prepare(app, p, adapter.project, 'job', adapter.save)
    assert list(adapter.blocks) == ['Existing'] and adapter.nets == before
    assert receipt['after']['sha256'] == data.digest(p['output_path'])
    assert receipt['after']['physical_port_ids'] == [2, 4, 6]
    assert receipt['settings_readback']['fmax'] == '8.0'  # Hz converted to actual MHz
    assert len(adapter.writes) == 1 and receipt['independent_dc_verified'] is False


@pytest.mark.parametrize('bad', ['type', 'outside', 'old_payload', 'output', 'mapping'])
def test_embedded_native_preconditions_do_not_create_or_write(tmp_path, bad):
    p, adapter, app = fixture_native(tmp_path)
    if bad == 'type': adapter.blocks['Existing']['type'] = 'Touchstone file'
    if bad == 'outside': adapter.blocks['Existing']['file'] = p['matrix_path']
    if bad == 'old_payload': p['expected_payload_sha256'] = 'f'*64
    if bad == 'output': Path(p['output_path']).write_text('keep')
    if bad == 'mapping': adapter.pins = lambda _: []
    with pytest.raises(ValueError): native.prepare(app, p, adapter.project, 'job', adapter.save)
    assert adapter.creates == 0 and not adapter.writes


@pytest.mark.parametrize('bad', ['fit', 'nets', 'saved'])
def test_native_fit_and_postsave_failures_never_report_success(tmp_path, bad):
    p, adapter, app = fixture_native(tmp_path, bad)
    with pytest.raises(ValueError): native.prepare(app, p, adapter.project, 'job', adapter.save)
    if bad != 'saved': assert not adapter.writes


def test_temporary_create_cannot_alter_existing_nets_before_fit(tmp_path):
    p, adapter, app = fixture_native(tmp_path, 'create_nets')
    with pytest.raises(ValueError, match='creation changed'):
        native.prepare(app, p, adapter.project, 'job', adapter.save)
    assert not adapter.writes
    assert not Path(native.paths(adapter.project, p['output_path'], 'job')[1]['A']).exists()


@pytest.mark.parametrize('bad', ['log', 'ref', 'labels', 'singular', 'shape', 'dc_passivity', 'reciprocity', 'actual_fit'])
def test_independent_fit_audit_rejects_bad_exports(tmp_path, bad):
    p, f, s, matrices = sample(tmp_path)
    _, paths, _ = native.paths(tmp_path/'model.cst', p['output_path'], 'audit')
    a, b, c, d = [v.copy() for v in matrices]
    if bad == 'singular': a[0] = 0
    if bad == 'shape': c = c[:-1]
    if bad == 'dc_passivity': d *= 20
    if bad == 'reciprocity': d[0, 1] = .1
    if bad == 'actual_fit': d += .05
    exports(paths, (a, b, c, d), ref=50 if bad == 'ref' else 75)
    if bad in ('dc_passivity', 'reciprocity'):
        p['limits']['fit_max_error'] = 10  # reach the independent DC predicate
    if bad == 'log': Path(paths['log']).write_text('unknown formulation')
    if bad == 'labels': Path(paths['log']).write_text(Path(paths['log']).read_text().replace('"1"', '"9"'))
    with pytest.raises((ValueError, np.linalg.LinAlgError)):
        data.audit_fit(paths, f, s, 75, p['limits'])


@pytest.mark.parametrize('bad', ['schema', 'hash', 'lf', 'unbound', 'source'])
def test_submission_errors_never_launch_cst(setup, monkeypatch, bad):
    p, *_ = sample(setup[2])
    if bad != 'unbound':
        _, em, _, _ = prepare_em_evidence(setup); p['em_job_id'] = em['job_id']
    if bad == 'schema': p['settings']['maximum_poles'] = True
    if bad == 'hash': p['matrix_sha256'] = 'f'*64
    if bad == 'lf': p['low_frequencies_hz'][0] += 20
    if bad == 'source':
        monkeypatch.setattr(service, 'verify_source', lambda *a: (_ for _ in ()).throw(ValueError('wrong run')))
    setup[-1].clear()
    with pytest.raises(ServiceError): submit(setup, data.OPERATION, {k:v for k,v in p.items() if k != 'project_id'})
    assert not setup[-1]


def test_saved_source_compares_every_complex_entry_and_physical_order(setup, monkeypatch):
    from tpc_service.sessions import em_qualification as q
    runtime, em, _, _ = prepare_em_evidence(setup)
    p, f, s, _ = sample(setup[2]); p['em_job_id'] = em['job_id']
    result = setup[3].with_suffix('')/'Result'; result.mkdir(parents=True)
    (result/'Storage.sdb').write_bytes(b'synthetic saved database')
    (result/'Model.log').write_text(source_log(p))
    em.update(started_at=1767225600, finished_at=1767225660)
    write(setup[2]/'jobs'/(em['job_id']+'.json'), em)
    def curves(path, args, values, *, consume):
        assert args['port_ids'] == [2, 4, 6]
        for i, a in enumerate(args['port_ids']):
            for j, b in enumerate(args['port_ids']): consume(a, b, f.tolist(), s[:, i, j].tolist())
        return {'matrix_sha256': 'native'}
    monkeypatch.setattr(q, 'saved_curves', curves)
    project = runtime.state()['projects']['p']
    assert service.verify_source(setup[2], project, p)['native_matrix_error'] < 1e-14
    s[-1, 2, 1] += .01
    with pytest.raises(ValueError): service.verify_source(setup[2], project, p)


def test_service_receipt_hb_gates_and_stale_queue(setup, monkeypatch):
    from tpc_service.sessions import operations
    runtime, em, report_path, _ = prepare_em_evidence(setup)
    p, adapter, app = fixture_native(setup[2]); p['em_job_id'] = em['job_id']
    # Use the owning fixture path; the fake native payload is under this path.
    state = runtime.state(); state['projects']['p']['path'] = str(adapter.project)
    state['projects']['p']['saved_digest'] = data.digest(adapter.project)
    runtime.update(projects=state['projects'])
    from tpc_service.sessions.workflow import marker
    write(marker(adapter.project), {'session_folder': str(setup[2].resolve()), 'project_id': 'p'})
    runtime.project = lambda *_: (app, runtime.state()['projects']['p'])
    runtime.save = lambda *_: adapter.save()
    monkeypatch.setattr(service, 'verify_source', lambda *a: {'saved_matrix': 'checked'})
    # Native fixture export naming uses its actual job identity.
    request = submit(setup, data.OPERATION, {k:v for k,v in p.items() if k != 'project_id'}, 'embedded')
    adapter.schematic.Block.ExtractStateSpaceModel = lambda *a: exports(native.paths(adapter.project, p['output_path'], request['job_id'])[1], adapter.matrices)
    generation = runtime.state()['projects']['p']['workflow']['em_generation']
    receipt = operations.execute(runtime, request)
    request.update(status='succeeded', result=receipt); write(setup[2]/'jobs'/(request['job_id']+'.json'), request)
    w = runtime.state()['projects']['p']['workflow']
    assert w['em_generation'] == generation and w['network_required'] and w['evidence'] is None
    with pytest.raises(ServiceError): hb(setup)
    report = read(report_path); report['artifacts'] += receipt['artifacts']; write(report_path, report)
    operations.execute(runtime, submit(setup, 'accept_workflow_evidence', dict(em_job_id=em['job_id'], report_path=str(report_path)), 'accept'))
    calls = []; monkeypatch.setattr(operations, 'circuit', lambda *a: calls.append('HB') or {})
    # Existing RF source/load native checks remain mandatory.
    old_select = adapter.select
    adapter.select = lambda kind, name: SimpleNamespace(DoesExist=lambda: True, GetProperty=lambda _:75) if name == 'RF' else old_select(kind, name)
    hbjob = hb(setup); operations.execute(runtime, hbjob); assert calls == ['HB']
    adapter.payload.write_text('changed'); calls.clear(); setup[-1].clear()
    with pytest.raises(ServiceError): hb(setup, request='again')
    assert not calls and not setup[-1]


def source_log(p):
    return ('Solver started at: 2026-01-01 00:00:00 +0000\n'
        'Mesh adaptation terminated because the desired accuracy limit is reached.\n'+
        ''.join(f'Calculation {i+1} (Frequency: {f} Hz)\n'+
            ''.join(f'Stimulation port: {port} Accuracy: 1e-9 Iterations: 12\n' for port in p['physical_port_ids'])
            for i, f in enumerate(p['low_frequencies_hz']))+
        'Finished the general purpose interpolative broadband frequency sweep:\n'
        'Creating parametric 1D results for Run ID 3')


@pytest.mark.parametrize('bad', ['interpolated', 'port', 'residual', 'coarse_mesh'])
def test_actual_lf_requires_final_mesh_native_excitations(tmp_path, bad):
    p, *_ = sample(tmp_path); log = source_log(p)
    assert len(data.actual_lf_samples(log, p)) == 9
    if bad == 'interpolated': log = log.replace('Frequency: 2000000.0 Hz', 'Frequency: 3000000.0 Hz')
    if bad == 'port': log = log.replace('Stimulation port: 6', 'Stimulation port: 7')
    if bad == 'residual': log = log.replace('Accuracy: 1e-9', 'Accuracy: 1e-3')
    if bad == 'coarse_mesh':
        log = log.replace('Mesh adaptation terminated because the desired accuracy limit is reached.\n', '')
        log = log.replace('Finished the general', 'Mesh adaptation terminated because the desired accuracy limit is reached.\nFinished the general')
    with pytest.raises(ValueError): data.actual_lf_samples(log, p)


def test_interpolated_lf_rejected_at_submission_before_launch(setup):
    runtime, em, _, _ = prepare_em_evidence(setup)
    p, *_ = sample(setup[2]); p['em_job_id'] = em['job_id']
    result = setup[3].with_suffix('')/'Result'; result.mkdir(parents=True)
    (result/'Storage.sdb').write_bytes(b'fixture')
    (result/'Model.log').write_text(source_log(p).replace('Frequency: 2000000.0 Hz', 'Frequency: 3000000.0 Hz'))
    setup[-1].clear()
    with pytest.raises(ServiceError, match='Actual final-mesh LF'):
        submit(setup, data.OPERATION, {k:v for k,v in p.items() if k != 'project_id'})
    assert not setup[-1]


def test_queued_source_change_rejected_before_project_acquisition(setup, monkeypatch):
    from tpc_service.sessions.operations import execute
    runtime, em, _, _ = prepare_em_evidence(setup)
    p, *_ = sample(setup[2]); p['em_job_id'] = em['job_id']
    monkeypatch.setattr(service, 'verify_source', lambda *a: {'checked': True})
    job = submit(setup, data.OPERATION, {k:v for k,v in p.items() if k != 'project_id'})
    Path(p['matrix_path']).write_bytes(b'changed after submission')
    runtime.project = lambda *_: pytest.fail('Rejected queue item must not acquire CST')
    with pytest.raises(ServiceError): execute(runtime, job)


def test_partial_native_failure_fences_hb_without_losing_em_generation(setup, monkeypatch):
    from tpc_service.sessions.worker import _finish_failed_job
    runtime, em, _, _ = prepare_em_evidence(setup)
    p, *_ = sample(setup[2]); p['em_job_id'] = em['job_id']
    monkeypatch.setattr(service, 'verify_source', lambda *a: {'checked': True})
    monkeypatch.setattr(native, 'prepare', lambda *a: (_ for _ in ()).throw(RuntimeError('native fit returned error')))
    job = submit(setup, data.OPERATION, {k:v for k,v in p.items() if k != 'project_id'})
    old = runtime.state()['projects']['p']['workflow']['em_generation']
    with pytest.raises(ServiceError) as caught: service.execute(runtime, job, native_app())
    state = runtime.state()
    _finish_failed_job(job, {'code': caught.value.code, 'message': str(caught.value), 'details': {}}, state)
    assert state['status'] == 'needs_reconcile'
    w = state['projects']['p']['workflow']
    assert w['em_generation'] == old and w['network_required'] and w['network_update'] is None


def test_old_worker_rejected_without_restart(setup, monkeypatch):
    import os
    from tpc_service.sessions.store import process_identity
    runtime, em, _, _ = prepare_em_evidence(setup)
    p, *_ = sample(setup[2]); p['em_job_id'] = em['job_id']
    state = runtime.state(); state['worker'] = process_identity(os.getpid())
    state['worker_capabilities'] = ['parameter-em-hb-v1', 'em-network-input-v1']
    runtime.update(worker=state['worker'], worker_capabilities=state['worker_capabilities'])
    setup[-1].clear()
    with pytest.raises(ServiceError, match='upgraded idle worker'):
        submit(setup, data.OPERATION, {k:v for k,v in p.items() if k != 'project_id'})
    assert not setup[-1] and runtime.state()['worker'] == state['worker']
