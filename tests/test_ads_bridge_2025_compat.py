import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/keysight-ads-simulation/scripts/ads_bridge_2025_compat.py'
spec = importlib.util.spec_from_file_location('ads_bridge_2025_compat', SCRIPT)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)

@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_known_source_is_patched_and_idempotent(newline):
    original = (repair.OLD + '\n' + repair.OLD_TEST).replace('\n', newline)
    fixed, changed = repair.transform(original)
    assert changed and newline in fixed
    assert repair.NEW in fixed.replace('\r\n', '\n')
    assert repair.transform(fixed) == (fixed, False)

def test_unknown_source_is_rejected():
    with pytest.raises(ValueError):
        repair.transform('unrecognized source')
