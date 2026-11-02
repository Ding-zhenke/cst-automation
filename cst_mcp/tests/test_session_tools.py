from pathlib import Path


def test_session_tools_explicit_registration_and_no_global_session(tmp_path, monkeypatch):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    monkeypatch.setattr(tools, 'TOOL_SPECS', list(tools.TOOL_SPECS))
    monkeypatch.setattr(tools, 'HANDLERS', dict(tools.HANDLERS))
    monkeypatch.setattr(tools, 'READ_TOOLS', set(tools.READ_TOOLS))
    monkeypatch.setattr(tools, 'WRITE_TOOLS', set(tools.WRITE_TOOLS))
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    a = tools.dispatch('ensure_cst_session', {'binding': 'a', 'request_id': 'a'})
    assert a['ok'] is True
    reference = a['session']
    value = tools.dispatch('get_cst_session', {'session_id': reference['session_id'],
                                             'credential': reference['credential']})
    assert value['ok'] is True
    assert value['session']['environment'] is None
    assert 'credential_hash' not in str(value)
    assert tools.dispatch('get_cst_session', {})['ok'] is False
    for name in ('submit_cst_session_operation', 'close_cst_session', 'resume_cst_session'):
        assert name in tools.WRITE_TOOLS
    assert 'get_cst_session_job' in tools.READ_TOOLS
    assert not list(tmp_path.rglob('worker.log'))
