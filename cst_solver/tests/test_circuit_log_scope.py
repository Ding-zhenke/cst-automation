from cst_solver.circuit.evidence import log_completion


OLD = 'Task: Parent\nERROR: earlier initialization failed\nTask time: old\nTotal time: old\n'


def test_unchanged_parent_error_is_missing_leaf_evidence_not_a_leaf_error():
    result = log_completion(OLD, OLD, 'HB')
    assert result['completed'] is False and result['log_changed'] is False
    assert result['log_errors'] is False
    assert result['historical_log_errors'] is True
    assert result['log_evidence_state'] == 'no_new_log_evidence'


def test_fresh_leaf_segment_is_separate_from_earlier_parent_errors():
    leaf = 'Task: HB\nTask time: new\nTotal time: new\n'
    result = log_completion(OLD, OLD+leaf, 'HB')
    assert result['completed'] is True
    assert result['log_errors'] is False and result['historical_log_errors'] is True


def test_fresh_error_still_blocks_completion():
    leaf = 'Task: HB\nERROR: current failure\nTask time: new\nTotal time: new\n'
    result = log_completion(OLD, OLD+leaf, 'HB')
    assert result['completed'] is False and result['log_errors'] is True
