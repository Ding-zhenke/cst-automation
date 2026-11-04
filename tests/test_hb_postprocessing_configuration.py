"""Configuration evidence must never become native binding/solver evidence."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from cst_automation.result_templates import (
    ResultTemplateError, inspect_embedded_python_result_template,
)
from cst_solver.circuit.native import (
    configure_hb_postprocessing_chain, inspect_hb_postprocessing_chain,
)


class Tasks:
    def __init__(self):
        self.rows = {'Sweep': ['parameter sweep', False],
                     'Sweep\\HB': ['spectral lines', False],
                     'Sweep\\Other': ['template', True]}
        self.order = ['Sweep\\HB', 'Sweep\\Other']
        self.writes = []

    def Reset(self): pass
    def Name(self, name): self.name = name
    def DoesExist(self): return self.name in self.rows
    def GetTypeForTask(self, name): return self.rows[name][0]
    def Type(self, kind): self.kind = kind
    def Create(self):
        self.rows[self.name] = [self.kind, False]
        self.order.append(self.name)
        self.writes.append(('create', self.name))
    def SetProperty(self, key, value):
        assert key == 'enabled'
        self.rows[self.name][1] = value == 'True'
        self.writes.append(('enabled', self.name))
    def GetProperty(self, key): return str(self.rows[self.name][1])
    def GetModelFolder(self, absolute): return '/generic/' + self.name
    def MoveInTree(self, parent, next_task):
        self.order.remove(self.name)
        index = self.order.index(parent + '\\' + next_task) if next_task else len(self.order)
        self.order.insert(index, self.name)
        self.writes.append(('move', self.name))


class Tree:
    def __init__(self, task): self.task = task
    def GetFirstChildName(self, root): return 'Tasks\\' + self.task.order[0]
    def GetNextItemName(self, item):
        index = self.task.order.index(item[len('Tasks\\'):]) + 1
        return 'Tasks\\' + self.task.order[index] if index < len(self.task.order) else ''


def schematic():
    task = Tasks()
    # No Update/Rebuild/Save/evaluation methods: an accidental run fails the test.
    return SimpleNamespace(SimulationTask=task, ResultTree=Tree(task))


def test_create_enables_chain_preserves_other_task_and_reads_order():
    app = schematic()
    report = configure_hb_postprocessing_chain(app, 'Sweep', 'Sweep\\HB', 'Sweep\\Post', create=True)
    assert report['task_order'] == ['Sweep\\Other', 'Sweep\\HB', 'Sweep\\Post']
    assert report['readback_verified'] is True
    assert report['binding_verified'] is report['solver_verified'] is False
    assert app.SimulationTask.rows['Sweep\\Other'] == ['template', True]
    assert report['native_save_required'] is True


def test_create_conflict_and_update_missing_fail_before_mutation():
    for post, create in [('Sweep\\Other', True), ('Sweep\\Missing', False)]:
        app = schematic()
        with pytest.raises(ValueError):
            configure_hb_postprocessing_chain(app, 'Sweep', 'Sweep\\HB', post, create=create)
        assert app.SimulationTask.writes == []


@pytest.mark.parametrize('hb,post', [('Sweep\\HB', 'Else\\Post'),
    ('Sweep\\HB', 'Sweep\\HB'), ('Sweep\\HB', 'Sweep\\Nested\\Post')])
def test_wrong_relationship_does_not_touch_native_tasks(hb, post):
    app = schematic()
    with pytest.raises(ValueError):
        configure_hb_postprocessing_chain(app, 'Sweep', hb, post, create=True)
    assert app.SimulationTask.writes == []


def test_readback_reports_disabled_and_wrong_order_without_mutation():
    app = schematic()
    report = inspect_hb_postprocessing_chain(app, 'Sweep', 'Sweep\\HB', 'Sweep\\Other')
    assert report['hb_then_post'] is True and report['readback_verified'] is False
    assert app.SimulationTask.writes == []
    app.SimulationTask.order.reverse()
    assert inspect_hb_postprocessing_chain(app, 'Sweep', 'Sweep\\HB', 'Sweep\\Other')['hb_then_post'] is False


@pytest.fixture
def resources(tmp_path):
    root = tmp_path / 'project'
    folder = root / 'Model/DS/native_resource'; folder.mkdir(parents=True)
    source = b'raise RuntimeError("never execute")\ndef define(settings): pass\ndef evaluate(settings): pass\n'
    (folder / 'Metric.rtpy').write_bytes(source)
    meta = folder / 'Metric.rtjson'
    meta.write_text(json.dumps({'template': {'python_module': {'path': 'Metric.rtpy', 'type': 'local_copy'},
                                            'settings': {'hb_task': 'Sweep\\HB'}}}), encoding='utf-8')
    # Deliberately not a complete native serialization; exact entry alone is NOT binding.
    (folder / 'Summary.rpp').write_text('Metric\n', encoding='utf-8')
    return root, folder, meta, source


def audit(resources, **kwargs):
    root, folder, meta, source = resources
    return inspect_embedded_python_result_template(root, metadata_path=meta,
        expected_settings={'hb_task': 'Sweep\\HB'}, **kwargs)


def test_resource_triple_is_audited_without_executing_or_claiming_binding(resources):
    report = audit(resources, expected_sha256=hashlib.sha256(resources[3]).hexdigest())
    assert report['resource_integrity_verified'] is True
    assert report['binding_verified'] is report['readback_verified'] is report['reopen_verified'] is False
    assert report['validation']['executed'] is False


def test_stale_hb_setting_is_rejected(resources):
    root, folder, meta, source = resources
    with pytest.raises(ResultTemplateError, match='settings'):
        inspect_embedded_python_result_template(root, metadata_path=meta, expected_settings={'hb_task': 'Old\\HB'})


@pytest.mark.parametrize('change', ['missing_summary', 'missing_module', 'wrong_summary', 'duplicate_entry', 'external_module'])
def test_partial_or_misdirected_registration_is_rejected(resources, change):
    root, folder, meta, source = resources
    if change == 'missing_summary': (folder / 'Summary.rpp').unlink()
    elif change == 'missing_module': (folder / 'Metric.rtpy').unlink()
    elif change == 'wrong_summary': (folder / 'Summary.rpp').write_text('Other\n')
    elif change == 'duplicate_entry': (folder / 'Summary.rpp').write_text('Metric\nMetric\n')
    else:
        data = json.loads(meta.read_text())
        data['template']['python_module']['path'] = '../Metric.rtpy'
        meta.write_text(json.dumps(data))
    with pytest.raises(ResultTemplateError): audit(resources)


def test_source_hash_conflict_is_rejected(resources):
    with pytest.raises(ResultTemplateError, match='SHA-256'):
        audit(resources, expected_sha256='0' * 64)


def test_malformed_module_metadata_is_a_structured_input_error(resources):
    root, folder, meta, source = resources
    meta.write_text(json.dumps({'template': {'python_module': []}}))
    with pytest.raises(ResultTemplateError, match='mappings'):
        audit(resources)
