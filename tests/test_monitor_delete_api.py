from types import SimpleNamespace

import pytest

from cst_solver.simulation.monitors import MonitorMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import validate_calls


def test_delete_field_monitor_emits_recorded_native_command():
    history = []
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda label, command: history.append((label, command)))))
    MonitorMixin.delete_field_monitor(app, 'e-field (f=315)')
    assert history == [('Delete field monitor: e-field (f=315)',
                        'Monitor.Delete "e-field (f=315)"')]


@pytest.mark.parametrize('name', ['', '  ', 'x"\nSolver.Start', 'a\nb', None])
def test_invalid_monitor_name_rejected_before_batch_execution(name):
    calls = [{'method': 'delete_field_monitor', 'args': [name]}]
    with pytest.raises(ServiceError):
        validate_calls(calls)


def test_named_monitor_delete_is_available_through_session_api():
    validate_calls([{'method': 'delete_field_monitor', 'args': ['e-field (f=315)']}])
