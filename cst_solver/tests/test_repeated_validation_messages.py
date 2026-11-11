from types import SimpleNamespace
import pytest
from cst_solver.validation import ValidationMixin


@pytest.mark.parametrize('kind,status', [('INFO', 'unverified'), ('WARNING', 'unverified'), ('ERROR', 'error')])
def test_identical_snapshots_do_not_erase_repeated_native_messages(kind, status):
    class App(ValidationMixin): pass
    app = App()
    message = {'type': kind, 'text': 'Repeated message'}
    app.cst_file = SimpleNamespace(get_messages=lambda: [message], model3d=SimpleNamespace(Rebuild=lambda: None))
    out = app.validate_model()
    assert out['repeated_snapshot'] is True
    assert out['message_consumption_verified'] is False
    assert out['native_run_message_binding_verified'] is False
    assert out['status'] == status
    assert out['messages'] == [message, message]


def test_single_read_does_not_claim_a_comparison():
    class App(ValidationMixin): pass
    app = App()
    app.cst_file = SimpleNamespace(get_messages=lambda: [])
    out = app.validate_model(rebuild=False)
    assert out['repeated_snapshot'] is None

