import pytest
from cst_automation.design_state import DesignState, identities


def config():
    return dict(geometry={'size': 1}, em={'mesh': 2}, static_sp={'dc': 0, 'pump': 0},
                ads_hb={'bias': 1}, analysis={'metric': 'loss'})


def test_dependency_scopes():
    a = config(); b = config(); b['ads_hb']['bias'] = 2
    x, y = identities(a), identities(b)
    assert x['em'] == y['em'] and x['static_sp'] == y['static_sp']
    assert x['ads_hb'] != y['ads_hb'] and x['analysis'] != y['analysis']
    b['geometry']['size'] = 2
    assert all(identities(a)[key] != identities(b)[key] for key in x)


def test_persistent_idempotence_and_preserved_failure(tmp_path):
    path = tmp_path/'state.sqlite'; cst = str(tmp_path/'model.cst')
    state = DesignState(path); state.register_project('p', cst, 'topology')
    state.begin_attempt('p', 'candidate', 'attempt', config())
    assert state.reserve('attempt', 'em', 'request')['new']
    assert not DesignState(path).reserve('attempt', 'em', 'request')['new']
    with pytest.raises(ValueError): state.reserve('attempt', 'em', 'other')
    state.finish('attempt', 'em', 'request', 'failed', {'reason': 'terminal native error'})
    with pytest.raises(ValueError): state.finish('attempt', 'em', 'request', 'complete', {'result': 'ok'})
    assert DesignState(path).snapshot('attempt')['stages']['em']['status'] == 'failed'
    changed = config(); changed['geometry']['size'] = 3
    with pytest.raises(ValueError): state.begin_attempt('p', 'candidate', 'attempt', changed)
    state.begin_attempt('p', 'other', 'another', changed)
    with pytest.raises(ValueError): state.register_project('p', str(tmp_path/'other.cst'), 'topology')


def test_concurrent_reservations_allow_one_request(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path/'state.sqlite'
    state = DesignState(path); state.register_project('p', str(tmp_path/'a.cst'), 't')
    state.begin_attempt('p', 'c', 'a', config())
    def reserve(request):
        try:
            return DesignState(path).reserve('a', 'em', request)['new']
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ('one', 'two')))
    assert sum(results) == 1
