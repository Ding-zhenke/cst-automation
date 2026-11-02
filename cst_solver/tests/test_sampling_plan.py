"""Pure plans and explicit log observations; never touch a CST project."""
import importlib
import sys

import pytest


@pytest.fixture
def sampling():
    return importlib.import_module('cst_solver.sampling')


def test_missing_sample_plan_excludes_verified_existing_points(sampling):
    plan = sampling.plan_missing_samples([.001, 5, .001], available_frequencies=[5, 8],
                                         frequency_unit='GHz', context_verified=True)
    assert plan['requested_frequencies'] == [.001, 5]
    assert plan['available_frequencies'] == [5, 8]
    assert plan['expected_new_frequencies'] == [.001]
    assert plan['reused_requested_frequencies'] == [5]
    assert plan['force_recalculate_old_samples'] is False
    assert plan['frequency_unit'] == 'GHz'


@pytest.mark.parametrize('available,verified', [(None, False), (None, True), ([5], False)])
def test_unverified_context_cannot_predict_actual_new_points(sampling, available, verified):
    plan = sampling.plan_missing_samples([.001], available_frequencies=available,
                                         frequency_unit='GHz', context_verified=verified)
    assert plan['expected_new_frequencies'] is None


def test_no_existing_results_is_distinct_from_unknown(sampling):
    plan = sampling.plan_missing_samples([.001], available_frequencies=[],
                                         frequency_unit='GHz', context_verified=True)
    assert plan['expected_new_frequencies'] == [.001]


def test_cached_requests_need_no_new_samples(sampling):
    plan = sampling.plan_missing_samples([5], available_frequencies=[5],
                                         frequency_unit='GHz', context_verified=True)
    assert plan['expected_new_frequencies'] == []


@pytest.mark.parametrize('frequencies', [[], [True], [-1], [0], [float('nan')], [float('inf')], ['5']])
def test_invalid_frequencies_fail_offline(sampling, frequencies):
    with pytest.raises(ValueError):
        sampling.plan_missing_samples(frequencies, frequency_unit='GHz')


def test_interrupted_wrong_frequency_is_not_an_accuracy_failure(sampling):
    plan = sampling.plan_missing_samples([.001], available_frequencies=[5, 8],
                                         frequency_unit='GHz', context_verified=True)
    report = sampling.assess_sample_execution(plan, [8], log_complete=False, aborted=True)
    assert report['status'] == 'aborted'
    assert report['frequency_status'] == 'mismatch' and report['unexpected_frequencies'] == [8]
    assert report['accuracy_status'] == 'not_assessed' and report['validation_passed'] is False
    assert report['observed_frequencies'] == [8] and report['requested_frequencies'] == [.001]


def test_complete_matching_points_do_not_prove_solver_accuracy(sampling):
    plan = sampling.plan_missing_samples([.001], available_frequencies=[5],
                                         frequency_unit='GHz', context_verified=True)
    report = sampling.assess_sample_execution(plan, [.001], log_complete=True, aborted=False)
    assert report['status'] == 'sample_set_matched'
    assert report['accuracy_status'] == 'not_assessed' and report['validation_passed'] is False


def test_incomplete_log_cannot_match_or_prove_missing_sample_failed(sampling):
    plan = sampling.plan_missing_samples([.001], available_frequencies=[],
                                         frequency_unit='GHz', context_verified=True)
    assert sampling.assess_sample_execution(plan, [.001], log_complete=False,
                                            aborted=False)['frequency_status'] == 'incomplete'


def test_unknown_expected_points_remain_unknown(sampling):
    plan = sampling.plan_missing_samples([.001], frequency_unit='GHz')
    assert sampling.assess_sample_execution(plan, [.001], log_complete=True,
                                            aborted=False)['frequency_status'] == 'unknown'


def test_pure_planning_does_not_import_native_sdk(sampling):
    before = {name for name in sys.modules if name == 'cst' or name.startswith('cst.')}
    plan = sampling.plan_missing_samples([5], frequency_unit='GHz')
    sampling.assess_sample_execution(plan, [], log_complete=False, aborted=False)
    assert {name for name in sys.modules if name == 'cst' or name.startswith('cst.')} == before


def test_complete_log_missing_target_is_frequency_mismatch_not_accuracy(sampling):
    plan = sampling.plan_missing_samples([.001], available_frequencies=[],
                                         frequency_unit='GHz', context_verified=True)
    report = sampling.assess_sample_execution(plan, [], log_complete=True, aborted=False)
    assert report['status'] == 'frequency_mismatch'
    assert report['not_observed_frequencies'] == [.001]
    assert report['accuracy_status'] == 'not_assessed'


def test_distinct_close_points_are_not_coalesced(sampling):
    plan = sampling.plan_missing_samples([5.000000000001], available_frequencies=[5],
                                         frequency_unit='GHz', context_verified=True)
    assert plan['expected_new_frequencies'] == [5.000000000001]


def test_unit_and_context_must_be_explicit(sampling):
    with pytest.raises(ValueError):
        sampling.plan_missing_samples([5], frequency_unit='project units')
    with pytest.raises(ValueError):
        sampling.plan_missing_samples([5], frequency_unit='GHz', context_verified='yes')


def test_observation_order_and_repeated_passes_do_not_change_point_set(sampling):
    plan = sampling.plan_missing_samples([5, 8], available_frequencies=[],
                                         frequency_unit='GHz', context_verified=True)
    report = sampling.assess_sample_execution(plan, [8, 5, 8], log_complete=True, aborted=False)
    assert report['frequency_status'] == 'matched'
    assert report['observed_frequencies'] == [8, 5]
