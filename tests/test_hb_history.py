"""Exercise the generated Post callback and the owned run entry without CST."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from cst_automation.result_templates import validate_python_result_template
from cst_automation.template_registration import prepare_python_result_registration
from cst_solver.circuit.hb_history import run_hb_history, write_hb_history_template


PATH = r'Tasks\Sweep\HB\Spectral Lines\Output'
RUN_ID = 'Schematic:RunID:7'


class Tree:
    def __init__(self):
        self.items, self.reads = {}, []
        self.arrays = {'x': [0, 2, 8], 'yre': [1, 2, 3], 'yim': [-1, -2, -3]}

    def GetResultIDsFromTreeItem(self, path):
        assert path == PATH
        return ['Schematic:RunID:0', RUN_ID]

    def GetResultFromTreeItem(self, path, result_id):
        self.reads.append((path, result_id))
        assert (path, result_id) == (PATH, RUN_ID)
        return SimpleNamespace(GetArray=self.arrays.__getitem__)

    def DoesTreeItemExist(self, name): return name in self.items
    def Reset(self): self.file = None
    def Name(self, name): self.name = name
    def File(self, file): self.file = file
    def Add(self): self.items[self.name] = self.file
    def Delete(self): pytest.fail('Historical results must never be deleted')
    def __getattr__(self, name): return lambda *args: None


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    path = tmp_path / 'model.cst'
    path.write_bytes(b'project')
    prj = SimpleNamespace(filename=lambda: str(path))
    tree = Tree()

    def result1d(_):
        points = []
        return SimpleNamespace(AppendXY=lambda x, y: points.append([float(x), float(y)]),
            Save=lambda file: Path(file).write_text(json.dumps(points)),
            Title=lambda *_: None, SetXLabelAndUnit=lambda *_: None,
            SetYLabelAndUnit=lambda *_: None, SetLogarithmicFactor=lambda *_: None)

    class Result0D:
        def SetData(self, value): self.value = value

    app = SimpleNamespace(ResultTree=tree, Result1D=result1d, Result0D=lambda _: Result0D())
    settings = {'namespace': 'responses', 'task_name': 'Sweep', 'adapter': 'test_hb_project_adapter',
        'revision': 'formula-v1', 'frequency_parameter': 'rf', 'direction_parameter': 'direction',
        'frequencies': [1, 2], 'directions': [0, 1],
        'parameter_units': {'size': 'mm', 'rf': 'GHz', 'direction': ''},
        'em_parameter_map': {'em_size': 'size'}, 'spectra': {PATH: {'x_unit': 'GHz', 'y_unit': 'V'}},
        'normalization': {'convention': 'complex probe voltage, peak'}}
    state = {'size': 1., 'rf': 1., 'direction': 0., 'token': 'native-a', 'verified': True}

    def params(): return {k: state[k] for k in settings['parameter_units']}

    def observe(**kwargs):
        return {'expected_parameters': params(), 'point_verified': state['verified'],
                'execution_id': state['token'], 'result_id': state.get('observed_id', RUN_ID),
                'configuration_sha256': 'a' * 64, 'em_source': {
                    'path': 'linked-em', 'sha256': 'b' * 64,
                    'parameters': {'em_size': state.get('em_size', state['size'])}},
                'evidence': {'hb_completion': 'test native observation'}}

    def derive(*, points, settings):
        # Deliberately depend on both directions and on each point's complex spectrum.
        values = [sum(point['spectra'][PATH]['yim'][1] for point in points if point['rf'] == f)
                  for f in settings['frequencies']]
        return {'Response': {'y': values, 'y_label': 'Imaginary voltage', 'y_unit': 'V'}}

    adapter = SimpleNamespace(observe=observe,
        read_parameters=lambda **kw: {**params(), **state.get('stored_override', {})}, derive=derive)
    monkeypatch.setitem(sys.modules, settings['adapter'], adapter)
    source = write_hb_history_template(tmp_path / 'history.rtpy').read_text(encoding='utf-8')
    assert validate_python_result_template(source)['valid']
    payload = prepare_python_result_registration(tmp_path / 'history.rtpy', result_name='History',
        template_name='History', group='Tests', result_type='0D', settings=settings)
    assert payload['History.rtpy'].decode('utf-8') == source
    template = {}
    exec(source, template)

    def point(rf, direction):
        state.update(rf=rf, direction=direction)
        return template['evaluate'](SimpleNamespace(result_id='Schematic:RunID:0'), app, prj, settings).value

    return SimpleNamespace(path=path, prj=prj, app=app, tree=tree, settings=settings,
                           state=state, point=point, root=tmp_path)


def test_automatic_complete_curves_keep_history_and_full_spectra(workflow):
    w = workflow
    assert [w.point(2, 1), w.point(1, 0), w.point(2, 0)] == [0, 0, 0]
    assert not w.tree.items
    assert w.point(1, 1) == 1
    original = {name: Path(file).read_bytes() for name, file in w.tree.items.items() if file}
    assert len(original) == 1
    assert json.loads(next(iter(original.values()))) == [[1, -4], [2, -4]]
    assert w.point(1, 1) == 1  # idempotent repeat, no new generation
    w.state.update(size=2., token='native-b')
    w.tree.arrays['yim'] = [0, -7, 5]
    assert [w.point(f, d) for f in [1, 2] for d in [0, 1]] == [0, 0, 0, 1]
    w.state.update(size=1., token='native-c')  # same parameter rerun, reused native ID
    assert [w.point(f, d) for f in [1, 2] for d in [0, 1]] == [0, 0, 0, 1]
    leaves = {name: Path(file).read_bytes() for name, file in w.tree.items.items() if file}
    assert len(leaves) == 3 and all(leaves[k] == v for k, v in original.items())
    assert len({name.rsplit('\\', 2)[0] for name in leaves}) == 2
    assert all(rid == RUN_ID for _, rid in w.tree.reads)
    points = [json.loads(p.read_text(encoding='utf-8')) for p in w.root.rglob('point-*.json')]
    assert len(points) == 12
    raw = next(p for p in points if p['parameters']['size'] == 1 and p['spectra'][PATH]['yim'][0] == -1)
    assert raw['spectra'][PATH] == {'x': [0, 2, 8], 'yre': [1, 2, 3], 'yim': [-1, -2, -3],
                                    'x_unit': 'GHz', 'y_unit': 'V'}
    assert raw['result_id'] == RUN_ID


def test_partial_rerun_never_completes_using_old_points(workflow):
    w = workflow
    assert [w.point(1, 0), w.point(1, 1), w.point(2, 0)] == [0, 0, 0]
    w.state['token'] = 'new-execution'
    assert w.point(2, 1) == 0
    assert not w.tree.items


@pytest.mark.parametrize('bad', [{'em_size': 9}, {'verified': False},
                                 {'stored_override': {'size': 9}}, {'token': None},
                                 {'observed_id': 'Schematic:RunID:0'}, {'observed_id': None}])
def test_unproven_input_does_not_read_or_publish(workflow, bad):
    workflow.state.update(bad)
    with pytest.raises(ValueError):
        workflow.point(1, 0)
    assert workflow.tree.reads == [] and not workflow.tree.items


def test_conflicting_duplicate_cannot_publish(workflow):
    w = workflow
    assert w.point(1, 0) == 0
    w.tree.arrays['yim'] = [4, 5, 6]
    with pytest.raises(ValueError, match='Conflicting'):
        w.point(1, 0)
    with pytest.raises(ValueError, match='Earlier HB point failed'):
        w.point(1, 1)
    assert not w.tree.items


def test_owned_entry_uses_real_callback_then_existing_save_contract(workflow):
    w = workflow
    w.state['token'] = None  # runner supplies one without relying on native ID.
    calls = []

    def run(task, *, mode, expected_results, reuse, note):
        assert (task, mode, reuse) == ('Sweep', 'network', 'never')
        calls.append('update')
        assert [w.point(f, d) for f in [1, 2] for d in [0, 1]] == [0, 0, 0, 1]
        calls.append('saved after callbacks')
        return {'status': 'succeeded', 'saved': True, 'execution_returned': True, 'run_token': 'owner-token'}

    api = SimpleNamespace(app=SimpleNamespace(cst_file=w.prj), run_checked=run)
    out = run_hb_history(api, 'Sweep', settings=w.settings, expected_results=[{'tree_path': PATH, 'run_id': 7}])
    assert calls == ['update', 'saved after callbacks']
    assert out['hb_history']['status'] == 'published'
    assert out['hb_history']['project_save_reported'] is True
    assert out['hb_history']['saved_readback_verified'] is False
    assert out['hb_history']['native_parametric_storage_verified'] is False
    receipt = Path(out['hb_history']['owner_receipt_path'])
    assert json.loads(receipt.read_text(encoding='utf-8'))['parent_run_token'] == 'owner-token'
    with pytest.raises(ValueError, match='execution'):
        w.point(1, 0)


def test_own_runner_distinguishes_parent_return_from_missing_callback(workflow):
    w = workflow
    api = SimpleNamespace(app=SimpleNamespace(cst_file=w.prj), run_checked=lambda *a, **kw:
                          {'status': 'succeeded', 'saved': True, 'execution_returned': True})
    out = run_hb_history(api, 'Sweep', settings=w.settings, expected_results=[{'tree_path': PATH, 'run_id': 7}])
    assert out['hb_history']['status'] == 'callback_not_observed'
    assert not w.tree.items


def test_native_write_failure_keeps_raw_points_and_does_not_retry(workflow, monkeypatch):
    w = workflow
    add = w.tree.Add

    def fail_on_curve():
        if w.tree.file:
            raise RuntimeError('native result add failed')
        add()

    monkeypatch.setattr(w.tree, 'Add', fail_on_curve)
    for f, d in [(1, 0), (1, 1), (2, 0)]:
        assert w.point(f, d) == 0
    with pytest.raises(RuntimeError, match='native result add failed'):
        w.point(2, 1)
    receipt = next(w.root.rglob('publication.json'))
    report = json.loads(receipt.read_text(encoding='utf-8'))
    assert report['status'] == 'publication_failed' and len(list(w.root.rglob('point-*.json'))) == 4
    assert Path(report['curves'][0]['signal_file']).is_file()
    monkeypatch.setattr(w.tree, 'Add', add)
    with pytest.raises(ValueError, match='Earlier HB point failed'):
        w.point(2, 1)
    assert not any(w.tree.items.values())
