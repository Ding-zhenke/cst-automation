# -*- coding: utf-8 -*-
"""CST 调用阻塞期间，查询/等待仍可得到诊断；任务不提前放行队列。"""
import threading

from tpc_service import RunService
from tpc_service.backends.base import ok_result


def test_blocked_job_wakes_wait_and_persists_dialog_evidence(tmp_path, monkeypatch):
    # 窗口数据替身是唯一外部边界；执行真正的服务、线程、守卫与落盘逻辑。
    try:
        from cst_solver import dialogs
    except ImportError:
        dialogs = None
    assert dialogs is not None, 'the dialog reader must be part of the installed package'
    release, entered = (threading.Event() for _ in range(2))
    visible = []
    monkeypatch.setattr(dialogs, 'list_dialogs', lambda only_cst=True, **kwargs: list(visible))

    class Backend:
        dialog_monitoring = True
        dialog_poll = 0.01
        dialog_timeout = None
        dialog_pid = 1234
        def build(self, **kwargs):
            entered.set()
            release.wait(4)
            return ok_result()

    project = tmp_path / 'template.cst'
    project.write_text('fake')
    service = RunService(str(tmp_path), backend=Backend())
    try:
        job_id = service.submit('build', project_path=str(project))['job_id']
        assert entered.wait(1)
        visible.append({'hwnd': 100, 'pid': 1234, 'process': 'cstd.exe',
                        'title': 'CST Error', 'body': 'Undefined variable: Ls',
                        'visible': True, 'blocking': True, 'buttons': []})
        status = service.wait(job_id, timeout=1)
        assert status.get('runtime_diagnostics', {}).get('state') == 'blocked_by_dialog'
        assert status['runtime_diagnostics']['dialogs'][0]['body'].endswith('Ls')
        assert status['status'] == 'running'
        assert service.worker.current == job_id
        saved = service.store.load(job_id).to_dict()
        assert saved['runtime_diagnostics']['attention_required'] is True
        assert any('Ls' in line for line in service.logs(job_id))
    finally:
        release.set()
        service.shutdown(wait=True, timeout=3)
    finished = service.get(job_id)
    assert finished['status'] == 'failed', 'an error popup must not turn into success'
    assert finished['error']['code'] == 'cst_dialog_blocked'


def test_monitor_target_is_reset_before_monitor_start(tmp_path, monkeypatch):
    from cst_solver import dialogs
    from tpc_service.backends.cst_backend import CstBackend
    seen_targets = []
    def scan(self):
        target = self.pid()
        seen_targets.append(target)
        if target == 1111:
            self._publish({'state': 'blocked_by_dialog', 'attention_required': True,
                           'dialogs': [{'title': 'previous job error'}]})
    monkeypatch.setattr(dialogs.DialogMonitor, '_scan', scan)
    class Backend(CstBackend):
        def build(self, **kwargs):
            # 监测的首轮可能早于 handler，因此 handler 内重置来不及。
            return ok_result()
    backend = Backend()
    backend.dialog_pid = 1111
    project = tmp_path / 'template.cst'
    project.write_text('fake')
    service = RunService(str(tmp_path), backend=backend)
    try:
        job_id = service.submit('build', project_path=str(project))['job_id']
        assert service.wait(job_id, timeout=2)['status'] == 'succeeded'
        assert backend.dialog_pid is None
        assert all(pid is None for pid in seen_targets)
    finally:
        service.shutdown(wait=True, timeout=2)
