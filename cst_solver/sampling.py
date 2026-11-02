"""Pure missing-sample plans and explicitly supplied native-log observations.

No CST SDK, file access, macro generation, log parsing or solver calls. Predicted
points are conditional on caller-verified cache identity and sampling settings.
"""
import math
from numbers import Real

__all__ = ['plan_missing_samples', 'assess_sample_execution']
_UNITS = ('Hz', 'kHz', 'MHz', 'GHz', 'THz')


def _frequencies(values):
    result = []
    try:
        for value in values:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError('frequencies must be finite positive numbers')
            value = float(value)
            if not math.isfinite(value) or value <= 0:
                raise ValueError('frequencies must be finite positive numbers')
            if value not in result:
                result.append(value)
    except (TypeError, OverflowError) as exc:
        raise ValueError('frequencies must be an iterable of finite positive numbers') from exc
    return result


def plan_missing_samples(requested_frequencies, *, frequency_unit,
                         available_frequencies=None, context_verified=False):
    """Plan requested missing samples without certifying any native point set.

    context_verified means the caller checked reusable results belong to the
    same mesh/parameters/sources/normalization, and that only explicit Single
    intervals remain (no extra automatic, monitor or adaptation sampling).
    False forces an unknown prediction. Units are explicit and never converted.
    """
    if frequency_unit not in _UNITS:
        raise ValueError('frequency_unit must explicitly be Hz, kHz, MHz, GHz or THz')
    if not isinstance(context_verified, bool):
        raise ValueError('context_verified must be bool')
    requested = _frequencies(requested_frequencies)
    if not requested:
        raise ValueError('at least one requested frequency is required')
    available = None if available_frequencies is None else _frequencies(available_frequencies)
    known = context_verified and available is not None
    return dict(intent='missing_requested_samples_only', frequency_unit=frequency_unit,
                requested_frequencies=requested, available_frequencies=available,
                context_verified=context_verified,
                expected_new_frequencies=[f for f in requested if f not in available] if known else None,
                reused_requested_frequencies=[f for f in requested if f in available] if known else None,
                force_recalculate_old_samples=False,
                status='conditional_plan' if known else 'unverified_context',
                actual_point_set='requires_native_log_verification')


def assess_sample_execution(plan, observed_frequencies, *, log_complete, aborted):
    """Compare one cycle's observed sample points, never solver accuracy.

    The caller must establish log/run identity and use the plan's frequency
    unit. Observations must come from actual frequency calculation records, not
    titles, requested settings, sweep summaries or a global last residual.
    """
    if not isinstance(log_complete, bool) or not isinstance(aborted, bool):
        raise ValueError('log_complete and aborted must be bool')
    if (plan.get('intent') != 'missing_requested_samples_only' or
            plan.get('frequency_unit') not in _UNITS or
            plan.get('force_recalculate_old_samples') is not False):
        raise ValueError('expected a missing-sample plan with forced recalculation disabled')
    observed = _frequencies(observed_frequencies)
    expected = plan['expected_new_frequencies']
    unexpected = None if expected is None else [f for f in observed if f not in expected]
    unseen = None if expected is None else [f for f in expected if f not in observed]
    frequency_status = ('unknown' if expected is None else
                        'mismatch' if unexpected or (log_complete and unseen) else
                        'incomplete' if not log_complete else 'matched')
    status = ('aborted' if aborted else
              'frequency_mismatch' if frequency_status == 'mismatch' else
              'sample_set_matched' if frequency_status == 'matched' else 'unverified')
    return dict(status=status, frequency_status=frequency_status, aborted=aborted,
                log_complete=log_complete, frequency_unit=plan['frequency_unit'],
                requested_frequencies=list(plan['requested_frequencies']),
                expected_new_frequencies=None if expected is None else list(expected),
                observed_frequencies=observed, unexpected_frequencies=unexpected,
                not_observed_frequencies=unseen,
                observation_source='caller_native_log_observations',
                accuracy_status='not_assessed', validation_passed=False)
