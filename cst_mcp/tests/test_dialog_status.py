# -*- coding: utf-8 -*-
"""SDK 阻塞时，MCP 查询必须透传独立监测的正文与待处理状态。"""
import threading

from cst_mcp import runtime, tools
from cst_solver import dialogs
from tpc_service.backends.base import ok_result


def test_job_status_exposes_dialog_while_original_call_is_blocked(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    class Backend:
        dialog_monitoring = True
        dialog_poll = 0.01
        dialog_timeout = None
        dialog_pid = 1234
        def build(self, **kwargs):
            entered.set()
            release.wait(4)
            return ok_result()
    def windows(**kwargs):
        if not entered.is_set() or release.is_set():
            return []
        return [{'hwnd': 100, 'pid': 1234, 'process': 'cstd.exe', 'visible': True,
                 'title': 'Error', 'body': 'Undefined variable: Ls', 'buttons': []}]
    monkeypatch.setattr(dialogs, 'list_dialogs', windows)
    project = tmp_path / 'template.cst'
    project.write_text('fake')
    runtime.reset()
    runtime.configure(workdir=str(tmp_path), backend=Backend())
    service = runtime.get_service()
    try:
        submitted = service.submit('build', project_path=str(project))
        assert entered.wait(1)
        service.wait(submitted['job_id'], timeout=1)
        payload = tools.dispatch('get_job_status', {'job_id': submitted['job_id']})
        job = payload['job']
        assert job['status'] == 'running'
        assert job.get('runtime_diagnostics', {}).get('state') == 'blocked_by_dialog'
        assert job['runtime_diagnostics']['dialogs'][0]['body'].endswith('Ls')
        assert any('弹窗' in note for note in payload['notes'])
    finally:
        release.set()
        service.shutdown(wait=True, timeout=3)
        runtime.reset()
