"""Regression tests with injected native objects; never connect to CST."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cst_solver.tests.test_ports_vba import _capture


def test_discrete_coordinates_do_not_depend_on_picks():
    _, code = _capture('create_discrete_port', 3, ['offset', 2, 0], [4, 5, 6])
    assert '.Voltage "1.0"' in code and '.Current "1.0"' in code
    assert 'Amplitude' not in code
    assert '.SetP1 "False", "offset", "2", "0"' in code
    assert '.SetP2 "False", "4", "5", "6"' in code


def test_native_targets_are_explicit_and_never_retry():
    from cst_solver.native import execute_vba, vba_capabilities
    model = Mock(side_effect=RuntimeError('native failure'))
    schematic = Mock(return_value='done')
    p = SimpleNamespace(model3d=SimpleNamespace(_execute_vba_code=model),
                        schematic=SimpleNamespace(execute_vba_code=schematic))
    assert vba_capabilities(p) == {'model3d': '_execute_vba_code',
                                   'schematic': 'execute_vba_code'}
    assert execute_vba(p, 'Sub Main\nEnd Sub', target='schematic', timeout=4) == 'done'
    schematic.assert_called_once_with('Sub Main\nEnd Sub', timeout=4)
    with pytest.raises(RuntimeError, match='native failure'):
        execute_vba(p, 'bad', target='model3d')
    model.assert_called_once_with('bad')
    assert schematic.call_count == 1
    with pytest.raises(ValueError):
        execute_vba(p, 'bad', target='guess')


def test_unsupported_native_target_fails_before_execution():
    from cst_solver.native import execute_vba
    with pytest.raises(NotImplementedError):
        execute_vba(SimpleNamespace(), 'bad', target='model3d')


def test_documented_circuit_objects_and_generated_net_readback():
    from cst_solver.native import circuit_probe_code, new_net_code
    code = circuit_probe_code('diff"probe', ('B', 'R1', '1'), ('B', 'R2', '2'))
    assert 'With CircuitProbe' in code and '.Name "diff""probe"' in code
    assert '.SetBlockPin "B", "R1", "1", True' in code
    assert '.SetRefBlockPin "B", "R2", "2"' in code
    code = new_net_code([('Block', 'R1', 0), ('Block', 'R2', 1)])
    assert '.AddComponentPorts("", ComponentPorts, False)' in code
    assert 'GeneratedNetName' in code and '.Apply' in code and '.GetNetName(' in code
    with pytest.raises(ValueError):
        new_net_code([('Block', 'R1', -1)])


def test_completed_max_passes_is_not_convergence():
    from cst_solver.convergence import mesh_convergence_report
    rows = [dict(frequency=5, pass_number=i, delta_s=d, residual=1e-6)
            for i, d in [(1, .1), (2, .04), (3, .03)]]
    r = mesh_convergence_report(rows, target=.01, expected_frequencies=[5],
                               max_passes=3, computation_completed=True,
                               warnings=['maximum passes reached'])
    assert r['computation_completed'] is True
    assert r['convergence'] == 'not_converged' and not r['validation_passed']
    assert r['samples'] == rows and r['warnings'] == ['maximum passes reached']
    assert r['frequencies'][0]['max_passes_reached']


def test_convergence_requires_all_frequencies_and_consecutive_passes():
    from cst_solver.convergence import mesh_convergence_report as report
    rows = [dict(frequency=5, pass_number=2, delta_s=.001)]
    assert report(rows, target=.01, expected_frequencies=[5, 10])['convergence'] == 'unknown'
    assert report(rows, target=.01, expected_frequencies=[5], required_passes=2)['convergence'] == 'unknown'
    rows.append(dict(frequency=5, pass_number=3, delta_s=.002))
    r = report(rows, target=.01, expected_frequencies=[5], required_passes=2,
               computation_completed=True)
    assert r['convergence'] == 'converged' and r['validation_passed']
    rows[-1]['delta_s'] = float('nan')
    with pytest.raises(ValueError):
        report(rows, target=.01, expected_frequencies=[5])


def test_glow_decoration_retains_raw_evidence_and_unknown_blocks(monkeypatch):
    from cst_solver import dialogs
    window = dict(hwnd=9, pid=7, process='cstd.exe', title='',
                  **{'class': 'QtitanTitleBarGlowWindow'}, visible=True,
                  owner=8, owner_pid=7, modal=True, is_dialog=True, responding=True)
    monkeypatch.setattr(dialogs, 'list_windows', lambda **kw: [window])
    monkeypatch.setattr(dialogs, '_user32', SimpleNamespace(IsWindowVisible=lambda hwnd: True))
    monkeypatch.setattr(dialogs, '_child_buttons', lambda hwnd: [])
    content = dict(body='', buttons=[], text_source='win32', text_readable=False,
                   text_complete=False, read_errors=[], has_progress=False)
    monkeypatch.setattr(dialogs, '_dialog_content', lambda *a: dict(content))
    d = dialogs.list_dialogs()[0]
    assert d['classification'] == 'decoration' and d['blocking'] is False
    assert d['owner'] == 8 and d['modal'] is True
    content['read_errors'] = ['access denied']
    assert dialogs.list_dialogs()[0]['blocking'] is True
    content.update(read_errors=[], body='real message', text_readable=True, text_complete=True)
    assert dialogs.list_dialogs()[0]['blocking'] is True


def test_unknown_monitor_failure_cannot_become_success():
    from cst_solver.dialogs import DialogMonitor
    m = DialogMonitor()
    m._publish(dict(state='monitor_error', attention_required=True, dialogs=[]))
    assert m.failure is not None


def test_known_error_requires_unchanged_process_identity(monkeypatch):
    from cst_solver import dialogs
    d = dict(hwnd=9, pid=7, title='History Error', body='no such method',
             text_complete=True, read_errors=[], process_creation_time='123',
             buttons=[dict(text='OK')])
    monkeypatch.setattr(dialogs, 'process_identity', lambda pid: {'creation_time': '456'})
    send = Mock()
    monkeypatch.setattr(dialogs, 'dismiss_dialogs', send)
    assert dialogs.acknowledge_known_error(d, expected_creation_time='123', button='OK')['action'] == 'identity_changed'
    send.assert_not_called()


def test_acknowledgement_requires_readback_and_rejects_unknown_title(monkeypatch):
    from cst_solver import dialogs
    d = dict(hwnd=9, pid=7, title='History Error', body='no such method',
             text_complete=True, read_errors=[], process_creation_time='123')
    monkeypatch.setattr(dialogs, 'process_identity', lambda pid: {'creation_time': '123'})
    send = Mock(return_value=[dict(action='clicked')])
    monkeypatch.setattr(dialogs, 'dismiss_dialogs', send)
    r = dialogs.acknowledge_known_error(d, expected_creation_time='123', button='OK')
    assert r['action'] == 'clicked' and r['readback_status'] == 'required'
    assert send.call_args.kwargs['expected_message'] == ('History Error', 'no such method')
    d['title'] = 'Unknown question'
    assert dialogs.acknowledge_known_error(d, expected_creation_time='123', button='OK')['action'] == 'unknown_error'
    assert send.call_count == 1


@pytest.mark.parametrize('creation_times,expected', [(['123', '123'], 'clicked'),
                                                    (['123', '456'], 'identity_changed')])
def test_dismiss_rechecks_identity_immediately_before_click(monkeypatch, creation_times, expected):
    from cst_solver import dialogs
    d = dict(hwnd=9, pid=7, process='cstd.exe', title='History Error', body='no such method',
             **{'class': '#32770'}, visible=True, text_complete=True, read_errors=[],
             process_creation_time='123', buttons=[dict(text='OK', hwnd=10)])
    monkeypatch.setattr(dialogs, 'list_dialogs', lambda **kw: [d])
    identities = iter(creation_times)
    monkeypatch.setattr(dialogs, 'process_identity', lambda pid: {'creation_time': next(identities)})
    monkeypatch.setattr(dialogs, '_pid_of', lambda hwnd: 7)
    monkeypatch.setattr(dialogs, '_pid_name', lambda pid: 'cstd.exe')
    monkeypatch.setattr(dialogs, '_control_text', lambda hwnd: 'OK')
    monkeypatch.setattr(dialogs, '_window_text', lambda hwnd: 'History Error')
    monkeypatch.setattr(dialogs, '_dialog_content', lambda *args: dict(d))
    send = Mock(return_value=True)
    monkeypatch.setattr(dialogs, '_send_button', send)
    result = dialogs.dismiss_dialogs(prefer=('OK',), pid=7, hwnd=9,
                                     expected_message=('History Error', 'no such method'),
                                     expected_creation_time='123')
    assert result[0]['action'] == expected
    assert send.call_count == int(expected == 'clicked')


def test_unknown_dialog_ownership_is_not_success():
    from cst_solver.dialogs import DialogMonitor
    monitor = DialogMonitor()
    monitor._publish(dict(state='dialog_detected', attention_required=True, dialogs=[{'pid': 7}]))
    assert monitor.failure is not None


def test_checked_session_never_retries_failed_open(monkeypatch):
    from cst_solver import host
    import cst_solver
    create = Mock(side_effect=RuntimeError('IPC unavailable'))
    monkeypatch.setattr(cst_solver, 'setup', create)
    monkeypatch.setattr(host, 'diagnose_host_session', lambda: {'desktop': 'interactive'})
    with pytest.raises(host.HostSessionError) as caught:
        host.open_host_session('example.cst')
    assert caught.value.code == 'cst_session_open_failed'
    create.assert_called_once_with('example.cst')


def test_service_preserves_monitor_error_code(tmp_path, monkeypatch):
    from cst_solver.dialogs import DialogMonitor
    from tpc_service import RunService
    from tpc_service.backends.fake import FakeBackend
    def start(monitor):
        monitor._publish(dict(state='monitor_error', attention_required=True, dialogs=[],
                              error={'code': 'cst_dialog_monitor_failed'}))
        return monitor
    monkeypatch.setattr(DialogMonitor, 'start', start)
    backend = FakeBackend()
    backend.dialog_monitoring = True
    backend.dialog_timeout = None
    path = tmp_path / 'fake.cst'
    path.write_text('fake')
    service = RunService(str(tmp_path / 'service'), backend=backend)
    try:
        job = service.submit('solve', project_path=str(path))
        service.shutdown(wait=True, timeout=2)
        r = service.get(job['job_id'])
        assert r['error']['code'] == 'cst_dialog_monitor_failed'
    finally:
        service.shutdown(wait=True, timeout=2)


def test_checked_session_refuses_unknown_desktop_and_reused_pid(monkeypatch):
    from cst_solver import host
    create = Mock()
    import cst_solver
    monkeypatch.setattr(cst_solver, 'setup', create)
    monkeypatch.setattr(host, 'diagnose_host_session', lambda: {'desktop': 'unknown'})
    with pytest.raises(host.HostSessionError):
        host.open_host_session()
    create.assert_not_called()
    monkeypatch.setattr(host, 'diagnose_host_session', lambda: {'desktop': 'interactive'})
    monkeypatch.setattr(host, 'process_identity', lambda pid: {'creation_time': '456'})
    with pytest.raises(host.HostSessionError):
        host.open_host_session(pid=7, expected_creation_time='123')
    create.assert_not_called()


def test_desktop_mismatch_is_restricted_not_interactive():
    from cst_solver.host import _classify_desktop
    assert _classify_desktop(True, 'Default', 'Default') == 'interactive'
    assert _classify_desktop(True, 'Restricted', 'Default') == 'restricted'
    assert _classify_desktop(True, None, 'Default') == 'unknown'
    assert _classify_desktop(False, 'Default', 'Default') == 'restricted'
