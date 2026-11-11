"""Pure data-first helpers for Gerber/Excellon round-trip acceptance."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping


def parse_ads_excellon(payload: str) -> dict[str, Any]:
    header = re.search(
        r"(?im)^\s*(METRIC|INCH)\s*,\s*(LZ|TZ)\s*,\s*([0]+)\.([0]+)\s*$",
        payload,
    )
    if not header:
        raise ValueError("Excellon unit, zero-suppression, or numeric-format header is missing")
    units = header.group(1).upper()
    suppression = header.group(2).upper()
    integer_digits = len(header.group(3))
    fractional_digits = len(header.group(4))
    total_digits = integer_digits + fractional_digits
    scale_to_mm = 1.0 if units == "METRIC" else 25.4

    tool_diameters: dict[str, float] = {
        match.group(1): float(match.group(2)) * scale_to_mm
        for match in re.finditer(r"(?im)^\s*T(\d+)C([0-9.+-Ee]+)\s*$", payload)
    }
    if not tool_diameters:
        raise ValueError("Excellon file contains no drill tool definitions")

    def coordinate(token: str) -> float:
        sign = -1.0 if token.startswith("-") else 1.0
        digits = token.lstrip("+-")
        if not digits.isdigit() or len(digits) > total_digits:
            raise ValueError(f"invalid Excellon coordinate: {token}")
        # ADS 2026 U1 emits METRIC,LZ while suppressing trailing zeroes in words.
        padded = (
            digits.ljust(total_digits, "0")
            if suppression == "LZ"
            else digits.rjust(total_digits, "0")
        )
        return sign * int(padded) / (10**fractional_digits) * scale_to_mm

    active_tool: str | None = None
    current_x: float | None = None
    current_y: float | None = None
    points: list[tuple[float, float]] = []
    records: list[dict[str, Any]] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        selection = re.fullmatch(r"T(\d+)", line, flags=re.IGNORECASE)
        if selection:
            active_tool = selection.group(1)
            continue
        if not line or line.startswith(";") or not re.match(r"^[XY]", line, flags=re.IGNORECASE):
            continue
        x_match = re.search(r"X([+-]?\d+)", line, flags=re.IGNORECASE)
        y_match = re.search(r"Y([+-]?\d+)", line, flags=re.IGNORECASE)
        if x_match:
            current_x = coordinate(x_match.group(1))
        if y_match:
            current_y = coordinate(y_match.group(1))
        if current_x is None or current_y is None or active_tool not in tool_diameters:
            raise ValueError("Excellon coordinate precedes X/Y state or a valid tool selection")
        points.append((current_x, current_y))
        records.append(
            {
                "x_mm": current_x,
                "y_mm": current_y,
                "tool": active_tool,
                "diameter_mm": tool_diameters[active_tool],
            }
        )
    return {
        "units": units.lower(),
        "suppression": suppression,
        "integer_digits": integer_digits,
        "fractional_digits": fractional_digits,
        "tool_diameters_mm": tool_diameters,
        "points_mm": points,
        "point_records": records,
    }


def require_non_nested_verification_workspace(
    source_workspace: Path | str, candidate: Path | str
) -> Path:
    source = Path(source_workspace).expanduser().resolve()
    target = Path(candidate).expanduser().resolve()
    if target == source or source in target.parents or target in source.parents:
        raise ValueError("verification workspace must not be nested in or contain the source workspace")
    if target.exists():
        raise FileExistsError(f"refusing to replace verification workspace: {target}")
    return target


def evaluate_cam_roundtrip_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    official_shapes = int(evidence.get("official_ads_drill_shapes", 0))
    source_count = int(evidence.get("source_pth_count", 0))
    parsed_count = int(evidence.get("parsed_drill_count", 0))
    materialized_count = int(evidence.get("materialized_verification_shapes", 0))
    parsed_count_matches_source = source_count > 0 and parsed_count == source_count
    independent_count_matches_source = (
        parsed_count_matches_source and materialized_count == source_count
    )
    official_count_matches_source = (
        parsed_count_matches_source and official_shapes == source_count
    )
    independent_drill_gate = (
        official_shapes == 0
        and independent_count_matches_source
        and evidence.get("coordinates_match_source") is True
        and bool(evidence.get("tool_diameters_mm"))
        and evidence.get("limitation_disclosed") is True
    )
    official_drill_gate = (
        official_shapes > 0
        and official_count_matches_source
        and evidence.get("coordinates_match_source") is True
    )
    pth_count_matches_source = (
        official_count_matches_source
        if official_shapes > 0
        else independent_count_matches_source
    )
    tolerance = float(evidence.get("copper_area_tolerance", -1.0))
    checks = {
        "gerber_layers_nonempty": evidence.get("required_gerber_layers_nonempty") is True,
        "outline_matches": evidence.get("outline_matches") is True,
        "top_copper_area_matches": tolerance >= 0.0
        and float(evidence.get("top_copper_relative_error", float("inf"))) <= tolerance,
        "bottom_copper_area_matches": tolerance >= 0.0
        and float(evidence.get("bottom_copper_relative_error", float("inf"))) <= tolerance,
        "pth_count_matches_source": pth_count_matches_source,
        "drill_content_verified": official_drill_gate or independent_drill_gate,
    }
    method = (
        "official_ads_import"
        if official_drill_gate
        else "independent_excellon_materialization"
        if independent_drill_gate
        else "not_verified"
    )
    errors = [name for name, passed in checks.items() if not passed]
    return {
        "checks": checks,
        "errors": errors,
        "drill_gate_method": method,
        "official_ads_drill_import_passed": official_drill_gate,
        "official_import_limitation": (
            "ADS importer materialized zero drill shapes; independent Excellon evidence was used"
            if independent_drill_gate
            else None
        ),
        "passed": not errors,
    }
