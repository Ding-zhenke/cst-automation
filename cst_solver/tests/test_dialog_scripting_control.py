import pytest
from cst_solver.dialogs import _is_scripting_control

QUIET_NOTICE = 'Quiet/Scripting mode is active and pop up windows are blocked.'

def observed():
 return dict(pid=59208, owner_pid=59208, owner_class='Qt683QWindowIcon',
             process='cstd.exe',
             title='CST Studio Suite 2026', **{'class':'Qt683QWindow'},
             body='', read_errors=[], buttons=[{'text':'Minimize'}, {'text':'Switch to Interactive Mode'}])

def test_observed_scripting_overlay():
 assert _is_scripting_control(observed())

@pytest.mark.parametrize('change', [dict(body='License error'), dict(read_errors=['UIA failed']),
 dict(owner_pid=1), dict(owner_class='#32770'), dict(buttons=[{'text':'OK'}]),
 dict(title='Error'), {'class':'Qt683QWindowIcon'}])
def test_unknown_or_error_window_is_never_exempted(change):
 w=observed(); w.update(change)
 assert not _is_scripting_control(w)


@pytest.mark.parametrize('change, blocking', [
    ({}, False),
    ({'body': QUIET_NOTICE + '\nRelease the license?'}, True),
    ({'body': 'Release the license?', 'buttons': [{'text': 'Yes'}, {'text': 'No'}]}, True),
    ({'body': 'Save changes?', 'buttons': [{'text': 'Save'}, {'text': 'Cancel'}]}, True),
    ({'body': '', 'text_readable': False, 'text_complete': False, 'read_errors': ['UIA timed out']}, True),
    ({'text_complete': False}, True),
    ({'truncated': True}, True),
    ({'owner_pid': 14}, True),
    ({'process': 'other.exe'}, True),
])
def test_scripting_notice_classification_reaches_monitor(monkeypatch, change, blocking):
    from types import SimpleNamespace
    from cst_solver import dialogs

    window = dict(observed(), hwnd=77, owner=66, visible=True, is_dialog=True,
                  modal=True, responding=True)
    content = dict(body=QUIET_NOTICE, buttons=window.pop('buttons'),
                   text_readable=True, text_complete=True, read_errors=[])
    for key, value in change.items():
        (window if key in window and key not in content else content)[key] = value
    monkeypatch.setattr(dialogs, 'list_windows', lambda **kwargs: [window])
    monkeypatch.setattr(dialogs, '_dialog_content', lambda *args: content)
    monkeypatch.setattr(dialogs, '_child_buttons', lambda hwnd: [])
    monkeypatch.setattr(dialogs, '_user32', SimpleNamespace(IsWindowVisible=lambda hwnd: True))

    snapshot, = dialogs.list_dialogs(pid=window['pid'])
    assert snapshot['blocking'] is blocking
    assert snapshot['error_code'] == ('cst_dialog_unknown' if blocking else None)
    assert snapshot.get('window_role') == (None if blocking else 'scripting_control')

    monitor = dialogs.DialogMonitor(pid=window['pid'], timeout=None, on_event=lambda event: None)
    monitor._scan()
    assert monitor.snapshot()['state'] == ('blocked_by_dialog' if blocking else 'clear')
    assert (monitor.failure is not None) is blocking

def test_controller_requires_complete_known_body():
 from cst_solver.dialogs import _is_startup_controller
 w=dict(pid=6216,owner_pid=6216,owner_class='Qt683QWindowIcon',title='CST DESIGN ENVIRONMENT 2026',**{'class':'Qt683QWindowIcon'},body='',read_errors=[],buttons=[])
 assert not _is_startup_controller(w)
 w['body']='Saving model'
 w.update(text_readable=True,text_complete=True,truncated=False)
 assert _is_startup_controller(w)
 for key,value in [('body',''),('body','License failure'),('buttons',[{'text':'OK'}]),
                   ('owner_pid',1),('title','Warning'),('text_complete',False),
                   ('text_readable',False),('truncated',True)]:
  changed=dict(w);changed[key]=value
  assert not _is_startup_controller(changed)


def test_observed_complete_save_progress_is_not_an_action_prompt():
 from cst_solver.dialogs import _is_startup_controller
 w=dict(pid=53304,owner_pid=53304,owner_class='Qt683QWindowIcon',
        title='CST DESIGN ENVIRONMENT 2026',**{'class':'Qt683QWindowIcon'},
        body='Saving model\n100%',read_errors=[],buttons=[],
        text_readable=True,text_complete=True,truncated=False)
 assert _is_startup_controller(w)
 for change in [dict(body='Saving model\n100%\nOverwrite existing file?'),
                dict(body='Saving model\n101%'),dict(body='Saving model\n-1%'),
                dict(buttons=[{'text':'Cancel'}]),dict(text_complete=False),
                dict(truncated=True),dict(read_errors=['UIA failed']),dict(owner_pid=1)]:
  changed=dict(w);changed.update(change)
  assert not _is_startup_controller(changed)


@pytest.mark.parametrize('still_visible', [True, False])
def test_dialog_that_disappears_during_read_is_not_a_current_blocker(monkeypatch, still_visible):
 from types import SimpleNamespace
 from cst_solver import dialogs
 w=dict(hwnd=77,pid=53304,owner_pid=53304,owner=66,owner_class='Qt683QWindowIcon',
        title='CST DESIGN ENVIRONMENT 2026',**{'class':'Qt683QWindowIcon'},
        visible=True,is_dialog=True,modal=True)
 monkeypatch.setattr(dialogs,'list_windows',lambda **kwargs:[w])
 monkeypatch.setattr(dialogs,'_dialog_content',lambda *args:dict(
     body='',text_readable=False,text_complete=False,read_errors=[],buttons=[],has_progress=False))
 monkeypatch.setattr(dialogs,'_child_buttons',lambda hwnd:[])
 monkeypatch.setattr(dialogs,'_user32',SimpleNamespace(IsWindowVisible=lambda hwnd:still_visible))
 result=dialogs.list_dialogs(pid=53304)
 if still_visible:
  assert len(result)==1 and result[0]['blocking'] and result[0]['needs_visual_inspection']
 else:
  assert result==[]
