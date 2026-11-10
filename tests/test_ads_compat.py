from types import SimpleNamespace

import pytest

from cst_automation.ads_compat import numbered_pin_point, set_repeated_values


def test_numbered_pin_point_requires_unambiguous_terminal_and_pin():
    pin = SimpleNamespace(snap_point=(1, 2))
    term = SimpleNamespace(is_numbered=True, term_number=2, inst_pins=[pin])
    inst = SimpleNamespace(inst_terms=[term])
    assert numbered_pin_point(inst, 2) == (1, 2)
    with pytest.raises(ValueError):
        numbered_pin_point(inst, 1)
    inst.inst_terms.append(term)
    with pytest.raises(ValueError):
        numbered_pin_point(inst, 2)
    inst.inst_terms.pop()
    term.inst_pins.append(pin)
    with pytest.raises(ValueError):
        numbered_pin_point(inst, 2)


def test_repeated_values_clone_before_assignment():
    class Repeats(list):
        def clone(self):
            self.append(object())

    class Parameter:
        repeats = Repeats([object()])

        @property
        def value(self):
            return self._value

        @value.setter
        def value(self, values):
            assert len(values) <= len(self.repeats)
            self._value = values

    param = Parameter()
    set_repeated_values(param, ['first', 'second'])
    assert param.value == ['first', 'second']
    assert len(param.repeats) == 2
    with pytest.raises(ValueError):
        set_repeated_values(param, [])
    with pytest.raises(ValueError):
        set_repeated_values(param, ['only'])
