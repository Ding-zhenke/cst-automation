"""Coordinate conversion for CST Design Studio's schematic position API."""

from __future__ import annotations


# Native schematic coordinates are centered on (0, 0), while Block.Position and
# ExternalPort.Position take coordinates in a 0..100000 canvas frame.  This
# offset is verified from CST-native Pos/GetPositionX/Y readbacks.
POSITION_ORIGIN_OFFSET = 50000


def native_position_to_cst(position):
    """Convert a signed native schematic point to CST's setter coordinate frame."""
    if (not isinstance(position, (list, tuple)) or len(position) != 2
            or any(type(value) not in (int, float) for value in position)
            or any(not -POSITION_ORIGIN_OFFSET < value < POSITION_ORIGIN_OFFSET
                   for value in position)):
        raise ValueError('Native position must contain two finite coordinates strictly within +/-50000')
    import math
    if any(not math.isfinite(value) for value in position):
        raise ValueError('Native position coordinates must be finite')
    return [value + POSITION_ORIGIN_OFFSET for value in position]
