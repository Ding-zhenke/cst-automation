from types import SimpleNamespace

def test_tasklist_output_does_not_inherit_forced_utf8(monkeypatch):
    import subprocess
    from cst_solver import dialogs
    seen={}
    def run(*args,**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stdout='"CST DESIGN ENVIRONMENT_AMD64.exe","123"',stderr='')
    monkeypatch.setattr(subprocess,'run',run)
    dialogs._refresh_pid_names()
    assert seen.get('errors')=='replace'
    if __import__('os').name=='nt': assert seen.get('encoding')=='mbcs'
