"""Small ADS database adapters; importing this module does not import ADS."""


def numbered_pin_point(instance, number):
    """Return the snap point for one unambiguous numbered terminal pin."""
    terminals = [t for t in instance.inst_terms if t.is_numbered and t.term_number == number]
    if len(terminals) != 1:
        raise ValueError(f"Expected one terminal numbered {number}; found {len(terminals)}")
    pins = list(terminals[0].inst_pins)
    if len(pins) != 1:
        raise ValueError(f"Expected one pin on terminal {number}; found {len(pins)}")
    return pins[0].snap_point


def set_repeated_values(parameter, values):
    """Expand repeated parameters before assigning; do not silently shrink them."""
    values = list(values)
    if not values:
        raise ValueError("At least one repeated value is required")
    count = len(parameter.repeats)
    if count > len(values):
        raise ValueError("Existing repeats exceed requested values")
    while count < len(values):
        parameter.repeats.clone()
        count += 1
    parameter.value = values
