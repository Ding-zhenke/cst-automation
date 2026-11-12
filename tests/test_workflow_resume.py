import pytest
from cst_automation.workflow_resume import missing_cases


def test_only_matching_completed_case_is_candidate():
    receipts = {'a': {'basis': 'v1', 'status': 'complete', 'artifact_sha256': 'a'*64},
                'b': {'basis': 'v0', 'status': 'complete', 'artifact_sha256': 'b'*64},
                'c': {'basis': 'v1', 'status': 'failed', 'artifact_sha256': 'c'*64}}
    assert missing_cases(['a', 'b', 'c', 'd'], receipts, 'v1') == ['b', 'c', 'd']
    assert missing_cases(['a'], receipts, 'v2') == ['a']


@pytest.mark.parametrize('cases', [[], ['a', 'a'], [''], [1]])
def test_invalid_inventory_rejected(cases):
    with pytest.raises(ValueError):
        missing_cases(cases, {}, 'v1')
