import pytest
from cst_solver.dialogs import _is_scripting_control

def observed():
 return dict(pid=59208, owner_pid=59208, owner_class='Qt683QWindowIcon',
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

def test_observed_empty_controller_is_not_a_modal_prompt():
 from cst_solver.dialogs import _is_startup_controller
 w=dict(pid=6216,owner_pid=6216,owner_class='Qt683QWindowIcon',title='CST DESIGN ENVIRONMENT 2026',**{'class':'Qt683QWindowIcon'},body='',read_errors=[],buttons=[])
 assert _is_startup_controller(w)
 w['body']='Saving model'
 assert _is_startup_controller(w)
 w['body']=''
 for key,value in [('body','License failure'),('buttons',[{'text':'OK'}]),('owner_pid',1),('title','Warning')]:
  changed=dict(w);changed[key]=value
  assert not _is_startup_controller(changed)
