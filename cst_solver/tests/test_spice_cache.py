"""Real temporary files with a supplied native boundary; no CST SDK."""
from types import SimpleNamespace

import pytest

from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import NativeAdapter, CircuitError


CARD = '.SUBCKT D A K\nD1 A K DM\n.MODEL DM D\n.ENDS D\n'


def setup_case(tmp_path, *, reference=None, pins=('A', 'K'), contents=CARD):
    source = tmp_path / 'approved.cir'
    source.write_text(CARD)
    project = tmp_path / 'case.cst'
    cache = tmp_path / 'case/Model/DS/Block/D1/model.cir'
    cache.parent.mkdir(parents=True)
    cache.write_text(contents)
    obj = SimpleNamespace(Reset=lambda: None, Name=lambda n: None, DoesExist=lambda: True,
        GetTypeName=lambda: 'SPICE', SetFile=lambda p: None, SetSpiceModel=lambda m: None,
        GetFile=lambda: reference if reference is not None else str(cache))
    bound = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(
        filename=lambda: str(project), schematic=SimpleNamespace(Block=obj))))
    bound.pins = lambda n: [{'pin_name': p} for p in pins]
    bound.spice_readback = lambda n: {'spice_model': 'D', 'spice_filter': 'PSPICE'}
    return CircuitAPI(SimpleNamespace(), adapter=bound), source, cache


def configure(api, source):
    return api.configure_nonlinear_model('D1', {'kind': 'spice', 'file': str(source), 'model': 'D'})


def test_internal_cache_is_verified_by_content_ports_and_owner(tmp_path):
    api, source, cache = setup_case(tmp_path)
    evidence = configure(api, source)['readback']['spice_verification']
    assert evidence['resolved_cache_path'] == str(cache)
    assert evidence['source_content_verified'] is True
    assert evidence['pin_mapping_verified'] is True
    assert evidence['cache_ownership_verified'] is True
    assert evidence['verification_complete'] is True
    assert evidence['saved_reopen_verified'] is False


def test_relative_reference_uses_project_directory_not_cwd(tmp_path, monkeypatch):
    api, source, cache = setup_case(tmp_path, reference='case/Model/DS/Block/D1/model.cir')
    elsewhere = tmp_path / 'elsewhere'; elsewhere.mkdir(); monkeypatch.chdir(elsewhere)
    assert configure(api, source)['readback']['spice_verification']['resolved_cache_path'] == str(cache)


@pytest.mark.parametrize('problem,field', [
    ('content', 'source_content_verified'), ('pins', 'pin_mapping_verified'),
    ('owner', 'cache_ownership_verified'), ('model', 'model_verified'),
])
def test_mismatch_retains_independent_evidence(tmp_path, problem, field):
    api, source, cache = setup_case(tmp_path, pins=('K', 'A') if problem == 'pins' else ('A', 'K'),
        contents=CARD + '* changed\n' if problem == 'content' else CARD)
    if problem == 'owner':
        wrong = tmp_path / 'other/Model/DS/Block/D1/model.cir'
        wrong.parent.mkdir(parents=True); wrong.write_text(CARD)
        api.adapter.schematic.Block.GetFile = lambda: str(wrong)
    if problem == 'model':
        api.adapter.spice_readback = lambda n: {'spice_model': 'OTHER', 'spice_filter': 'PSPICE'}
    with pytest.raises(CircuitError) as caught:
        configure(api, source)
    assert caught.value.code == 'circuit_build_partial'
    assert caught.value.details['readback']['spice_verification'][field] is False


def test_unreadable_cache_does_not_fall_back_to_source(tmp_path):
    api, source, cache = setup_case(tmp_path); cache.unlink()
    evidence = configure(api, source)['readback']['spice_verification']
    assert evidence['source_content_verified'] is None
    assert evidence['cache_snapshot']['error']
    assert evidence['verification_complete'] is False


def test_dependencies_are_unknown_even_with_matching_top_level(tmp_path):
    api, source, cache = setup_case(tmp_path)
    card = CARD + '.include "external.lib"\n'
    source.write_text(card); cache.write_text(card)
    evidence = configure(api, source)['readback']['spice_verification']
    assert evidence['source_content_verified'] is True
    assert evidence['dependency_closure_verified'] is None
    assert evidence['verification_complete'] is False


def test_same_path_changed_since_approval_fails_content_verification(tmp_path):
    from cst_automation.circuit_models import nonlinear_model_settings
    from cst_automation.spice_identity import verify_spice_identity
    api, source, cache = setup_case(tmp_path)
    settings = nonlinear_model_settings({'kind': 'spice', 'file': str(source), 'model': 'D'})
    source.write_text(CARD + '* changed\n')
    evidence = verify_spice_identity(settings, str(source), str(tmp_path/'case.cst'), 'D1',
        {'spice_model': 'D', 'spice_filter': 'PSPICE'}, [{'pin_name': 'A'}, {'pin_name': 'K'}])
    assert evidence['source_content_verified'] is False


def test_source_reference_does_not_claim_cache_ownership(tmp_path):
    api, source, _ = setup_case(tmp_path)
    api.adapter.schematic.Block.GetFile = lambda: str(source)
    evidence = configure(api, source)['readback']['spice_verification']
    assert evidence['source_content_verified'] is True
    assert evidence['reference_kind'] == 'source_reference'
    assert evidence['cache_ownership_verified'] is None
    assert evidence['verification_complete'] is False


def test_relative_reference_without_project_is_unknown(tmp_path):
    api, source, _ = setup_case(tmp_path, reference='case/Model/DS/Block/D1/model.cir')
    api.adapter.app.cst_file.filename = lambda: None
    evidence = configure(api, source)['readback']['spice_verification']
    assert evidence['resolved_cache_path'] is None
    assert evidence['source_content_verified'] is None
    assert 'requires bound project' in evidence['resolution_error']


def test_cross_project_cache_is_rejected_even_when_contents_match(tmp_path):
    api, source, _ = setup_case(tmp_path)
    wrong = tmp_path / 'other/Model/DS/Block/D1/model.cir'
    wrong.parent.mkdir(parents=True); wrong.write_text(CARD)
    api.adapter.schematic.Block.GetFile = lambda: str(wrong)
    with pytest.raises(CircuitError) as caught:
        configure(api, source)
    evidence = caught.value.details['readback']['spice_verification']
    assert evidence['source_content_verified'] is True
    assert evidence['cache_ownership_verified'] is False


@pytest.mark.parametrize('relative', ['Model/DS/Block/model.cir', 'Model/DS/Block/123/model.cir',
                                      'Model/DS/Block/OTHER/model.cir'])
def test_uncalibrated_internal_layout_is_unknown(tmp_path, relative):
    api, source, cache = setup_case(tmp_path)
    alternate = tmp_path / 'case' / relative
    alternate.parent.mkdir(parents=True, exist_ok=True); alternate.write_text(CARD)
    api.adapter.schematic.Block.GetFile = lambda: str(alternate)
    evidence = configure(api, source)['readback']['spice_verification']
    assert evidence['source_content_verified'] is True
    assert evidence['cache_ownership_verified'] is None
    assert evidence['verification_complete'] is False


def test_explicit_dialect_mismatch_is_retained(tmp_path):
    api, source, _ = setup_case(tmp_path)
    api.adapter.schematic.Block.SetSpiceFilter = lambda d: None
    with pytest.raises(CircuitError) as caught:
        api.configure_nonlinear_model('D1', {'kind': 'spice', 'file': str(source),
            'model': 'D', 'dialect': 'HSPICE'})
    assert caught.value.details['readback']['spice_verification']['dialect_verified'] is False


@pytest.mark.parametrize('card', [
    '.SUBCKT D A K PARAMS: V=1\n.ENDS\n',
    '.SUBCKT D A\n+ K\n.ENDS\n',
    CARD + CARD,
    '.SUBCKT OTHER A K\n.ENDS\n',
])
def test_unparsed_ports_are_unknown_not_invented(tmp_path, card):
    api, source, cache = setup_case(tmp_path)
    source.write_text(card); cache.write_text(card)
    evidence = configure(api, source)['readback']['spice_verification']
    assert evidence['source_content_verified'] is True
    assert evidence['pin_mapping_verified'] is None
    assert evidence['source_parse_error']
    assert evidence['verification_complete'] is False
