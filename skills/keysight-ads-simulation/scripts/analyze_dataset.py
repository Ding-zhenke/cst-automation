"""Read ADS ``.ds`` data directly and apply a circuit-appropriate smoke analysis."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Iterable

from ads_common import base_status, json_safe, print_json, voltage_to_dbm, write_json


ANALYSIS_KINDS = (
    "inventory",
    "voltage-spectrum",
    "sparameter",
    "oscillator",
    "state-sweep",
)


def _select_block(block_names: list[str], requested: str | None) -> str:
    if requested is not None:
        if requested not in block_names:
            raise KeyError(f"Block '{requested}' is missing; available: {block_names}")
        return requested
    if len(block_names) != 1:
        raise ValueError(
            "Dataset has multiple blocks; select one explicitly with --block: "
            f"{block_names}"
        )
    return block_names[0]


def _validate_complex_metric(value: complex, *, require_nonzero: bool) -> complex:
    metric = complex(value)
    if not (math.isfinite(metric.real) and math.isfinite(metric.imag)):
        raise ValueError(f"Selected metric is not finite: {metric}")
    if require_nonzero and abs(metric) == 0:
        raise ValueError("Selected metric is numerically zero")
    return metric


def _find_column(frame, requested: str):
    """Find an ADS column, accepting known capitalization changes across releases."""
    for column in frame.columns:
        if str(column) == requested:
            return column
    folded = requested.casefold()
    matches = [column for column in frame.columns if str(column).casefold() == folded]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise KeyError(
            f"Variable/column '{requested}' is ambiguous after case folding: "
            f"{[str(item) for item in matches]}"
        )
    raise KeyError(
        f"Variable/column '{requested}' is missing; available: "
        f"{[str(c) for c in frame.columns]}"
    )


def _row_for_mix(frame, mix_index: list[int]):
    mask = None
    for index, wanted in enumerate(mix_index, start=1):
        column = _find_column(frame, f"Mix[{index}]")
        condition = frame[column] == wanted
        mask = condition if mask is None else (mask & condition)
    matches = frame[mask]
    if len(matches) != 1:
        raise LookupError(f"Expected one row for mix index {mix_index}, found {len(matches)}")
    return matches.iloc[0]


def _row_for_frequency(frame, target_hz: float, tolerance_hz: float):
    if not math.isfinite(target_hz):
        raise ValueError("target_frequency_hz must be finite")
    if not math.isfinite(tolerance_hz) or tolerance_hz < 0:
        raise ValueError("frequency_tolerance_hz must be finite and nonnegative")
    frequency = _find_column(frame, "freq")
    frequency_values = frame[frequency].astype(float)
    if not frequency_values.map(math.isfinite).all():
        raise ValueError("Dataset frequency axis contains NaN or Inf")
    distance = (frequency_values - target_hz).abs()
    if distance.empty:
        raise LookupError("Dataset block has no frequency rows")
    position = distance.idxmin()
    if float(distance.loc[position]) > tolerance_hz:
        raise LookupError(
            f"Nearest frequency is outside tolerance: error={float(distance.loc[position])} Hz, "
            f"tolerance={tolerance_hz} Hz"
        )
    return frame.loc[position]


def sparameter_to_db(value: complex | float) -> float:
    """Convert a dimensionless S parameter with ``20*log10(abs(S))``."""
    magnitude = abs(complex(value))
    return float("-inf") if magnitude == 0 else 20.0 * math.log10(magnitude)


def _finite_complex_series(frame, column, *, require_nonzero: bool = False) -> list[complex]:
    values = [
        _validate_complex_metric(complex(value), require_nonzero=False)
        for value in frame[column]
    ]
    if require_nonzero and not any(abs(value) > 0 for value in values):
        raise ValueError(f"Variable '{column}' contains no finite nonzero value")
    return values


def _inventory_finite_values(frame) -> tuple[int, list[str]]:
    finite_count = 0
    numeric_columns: list[str] = []
    for column in frame.columns:
        column_count = 0
        for raw in frame[column]:
            try:
                value = complex(raw)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value.real) and math.isfinite(value.imag):
                column_count += 1
        if column_count:
            numeric_columns.append(str(column))
            finite_count += column_count
    if finite_count == 0:
        raise ValueError("Dataset block contains no finite numeric values")
    return finite_count, numeric_columns


def analyze_frame(
    frame,
    *,
    kind: str,
    variable: str | None = None,
    reference_ohms: float = 50.0,
    state_column: str | None = None,
    required_states: Iterable[Any] | None = None,
    require_nonzero: bool = False,
) -> dict[str, Any]:
    """Analyze an already materialized ADS data frame without importing ADS APIs."""
    normalized_kind = str(kind).strip().casefold()
    if normalized_kind not in ANALYSIS_KINDS:
        raise ValueError(f"Unknown analysis kind '{kind}'; choose from: {ANALYSIS_KINDS}")
    if len(frame) == 0:
        raise ValueError("Dataset block is empty")

    result: dict[str, Any] = {
        "kind": normalized_kind,
        "row_count": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
    }
    if normalized_kind == "inventory":
        finite_count, numeric_columns = _inventory_finite_values(frame)
        result.update(
            {
                "finite_numeric_value_count": finite_count,
                "numeric_columns": numeric_columns,
            }
        )
        return result

    if variable is None:
        raise ValueError(f"--variable is required for {normalized_kind} analysis")
    variable_column = _find_column(frame, variable)
    values = _finite_complex_series(
        frame, variable_column, require_nonzero=require_nonzero
    )
    result["selected_variable"] = str(variable_column)

    if normalized_kind == "voltage-spectrum":
        if not math.isfinite(reference_ohms) or reference_ohms <= 0:
            raise ValueError("reference_ohms must be finite and positive")
        result.update(
            {
                "unit": "dBm",
                "reference_ohms": reference_ohms,
                "values_dbm": [voltage_to_dbm(value, reference_ohms) for value in values],
                "nonzero_value_count": sum(abs(value) > 0 for value in values),
            }
        )
        return result

    if normalized_kind == "sparameter":
        result.update(
            {
                "unit": "dB",
                "values_db": [sparameter_to_db(value) for value in values],
                "magnitudes": [abs(value) for value in values],
            }
        )
        return result

    if normalized_kind == "oscillator":
        frequency_column = _find_column(frame, "freq")
        candidates: list[tuple[float, complex]] = []
        for frequency_raw, value in zip(frame[frequency_column], values):
            frequency = float(frequency_raw)
            if not math.isfinite(frequency):
                raise ValueError("Oscillator frequency axis contains NaN or Inf")
            if frequency > 0 and abs(value) > 0:
                candidates.append((frequency, value))
        if not candidates:
            raise ValueError("No positive-frequency finite nonzero oscillator fundamental found")
        frequency, fundamental = min(candidates, key=lambda item: item[0])
        result.update(
            {
                "unit": "voltage_phasor",
                "oscillation_frequency_hz": frequency,
                "fundamental": json_safe(fundamental),
                "fundamental_magnitude": abs(fundamental),
            }
        )
        return result

    selected_state_column = _find_column(frame, state_column or "state")
    available_states = list(dict.fromkeys(frame[selected_state_column].tolist()))
    requested_states = list(required_states or ())
    if not requested_states:
        raise ValueError("required_states must name at least one RF-switch state")
    missing = [state for state in requested_states if state not in available_states]
    if missing:
        raise LookupError(
            f"Required RF-switch states are missing: {missing}; available: {available_states}"
        )
    result.update(
        {
            "state_column": str(selected_state_column),
            "states": requested_states,
            "available_states": available_states,
            "finite_value_count": len(values),
        }
    )
    return result


def _export_analysis_csv(frame, destination: Path, *, kind: str | None, variable: str | None,
                         reference_ohms: float) -> None:
    export = frame.copy()
    if variable is not None:
        variable_column = _find_column(export, variable)
        export[f"{variable}_real"] = export[variable_column].map(lambda item: complex(item).real)
        export[f"{variable}_imag"] = export[variable_column].map(lambda item: complex(item).imag)
        export[f"{variable}_magnitude"] = export[variable_column].map(
            lambda item: abs(complex(item))
        )
        if kind == "sparameter":
            export[f"{variable}_dB"] = export[variable_column].map(sparameter_to_db)
        elif kind in (None, "voltage-spectrum"):
            export[f"{variable}_dBm_{reference_ohms:g}ohm"] = export[variable_column].map(
                lambda item: voltage_to_dbm(complex(item), reference_ohms)
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(destination, index=False)


def analyze_dataset(
    dataset_path: str | Path,
    *,
    block: str | None = None,
    kind: str | None = None,
    variable: str | None = None,
    target_frequency_hz: float | None = None,
    frequency_tolerance_hz: float = 1.0,
    mix_index: list[int] | None = None,
    reference_ohms: float = 50.0,
    require_nonzero: bool = False,
    state_column: str | None = None,
    required_states: Iterable[Any] | None = None,
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Open an ADS dataset and return a JSON-safe inventory or selected metric.

    Omitting ``kind`` preserves the original voltage-phasor behavior used by
    the mixer and reopen helpers.
    """
    import keysight.ads.dataset as dataset

    if not math.isfinite(reference_ohms) or reference_ohms <= 0:
        raise ValueError("reference_ohms must be finite and positive")
    source = Path(dataset_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Dataset not found: {source}")

    with dataset.open_dataset_for_reading(source) as opened:
        block_names = list(opened.keys())
        if not block_names:
            raise ValueError(f"Dataset contains no variable blocks: {source}")
        selected_block = _select_block(block_names, block)
        frame = opened[selected_block].to_dataframe().reset_index()

    if len(frame) == 0:
        raise ValueError(f"Dataset block is empty: {selected_block}")
    try:
        frequency_column = _find_column(frame, "freq")
    except KeyError:
        frequency_column = None
    if frequency_column is not None:
        frequency_values = frame[frequency_column].astype(float)
        if not frequency_values.map(math.isfinite).all():
            raise ValueError("Dataset frequency axis contains NaN or Inf")

    result: dict[str, Any] = {
        "dataset": str(source),
        "blocks": block_names,
        "selected_block": selected_block,
        "row_count": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
        "target": None,
    }

    if kind is not None:
        analysis = analyze_frame(
            frame,
            kind=kind,
            variable=variable,
            reference_ohms=reference_ohms,
            state_column=state_column,
            required_states=required_states,
            require_nonzero=require_nonzero,
        )
        result.update(analysis)
        if variable is not None and (mix_index is not None or target_frequency_hz is not None):
            variable_column = _find_column(frame, variable)
            if mix_index is not None:
                row = _row_for_mix(frame, mix_index)
                selector: dict[str, Any] = {"mix_index": mix_index}
            else:
                row = _row_for_frequency(frame, float(target_frequency_hz), frequency_tolerance_hz)
                selector = {
                    "target_frequency_hz": target_frequency_hz,
                    "frequency_tolerance_hz": frequency_tolerance_hz,
                }
            value = _validate_complex_metric(
                complex(row[variable_column]), require_nonzero=require_nonzero
            )
            target = {
                **selector,
                "frequency_hz": (
                    float(row[frequency_column]) if frequency_column is not None else None
                ),
                "value": json_safe(value),
                "magnitude": abs(value),
            }
            if kind == "sparameter":
                target["value_db"] = sparameter_to_db(value)
                target["unit"] = "dB"
            elif kind == "voltage-spectrum":
                target["power_dbm"] = voltage_to_dbm(value, reference_ohms)
                target["reference_ohms"] = reference_ohms
            result["target"] = target
    elif variable is not None:
        # Legacy voltage-spectrum metric path retained for existing callers.
        variable_column = _find_column(frame, variable)
        _finite_complex_series(frame, variable_column)
        result["selected_variable"] = str(variable_column)
        if mix_index is not None:
            row = _row_for_mix(frame, mix_index)
            selector = {"mix_index": mix_index}
        elif target_frequency_hz is not None:
            row = _row_for_frequency(frame, target_frequency_hz, frequency_tolerance_hz)
            selector = {
                "target_frequency_hz": target_frequency_hz,
                "frequency_tolerance_hz": frequency_tolerance_hz,
            }
        else:
            row = None
            selector = {}

        if row is not None:
            value = _validate_complex_metric(
                complex(row[variable_column]), require_nonzero=require_nonzero
            )
            frequency_hz = float(row[frequency_column]) if frequency_column is not None else None
            power_dbm = voltage_to_dbm(value, reference_ohms)
            result["target"] = {
                **selector,
                "frequency_hz": frequency_hz,
                "value": json_safe(value),
                "magnitude": abs(value),
                "power_dbm": power_dbm,
                "reference_ohms": reference_ohms,
            }
            if reference_ohms == 50.0:
                result["target"]["power_dbm_50ohm"] = power_dbm
    else:
        # A no-kind/no-variable call is a backwards-compatible inventory smoke.
        result.update(analyze_frame(frame, kind="inventory"))

    if csv_path is not None:
        destination = Path(csv_path).resolve()
        _export_analysis_csv(
            frame,
            destination,
            kind=kind,
            variable=variable,
            reference_ohms=reference_ohms,
        )
        result["csv"] = str(destination)
    return result


def _state_scalar(value: str) -> Any:
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--block")
    parser.add_argument("--kind", choices=ANALYSIS_KINDS)
    parser.add_argument("--variable")
    parser.add_argument("--target-frequency-hz", type=float)
    parser.add_argument("--frequency-tolerance-hz", type=float, default=1.0)
    parser.add_argument("--mix-index", nargs="+", type=int)
    parser.add_argument("--reference-ohms", type=float, default=50.0)
    parser.add_argument("--require-nonzero", action="store_true")
    parser.add_argument("--state-column")
    parser.add_argument("--required-state", action="append", default=[])
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    status = base_status("analyze_dataset")
    status["dataset"] = str(args.dataset.resolve())
    try:
        kind = args.kind
        if kind is None and args.variable is None:
            kind = "inventory"
        result = analyze_dataset(
            args.dataset,
            block=args.block,
            kind=kind,
            variable=args.variable,
            target_frequency_hz=args.target_frequency_hz,
            frequency_tolerance_hz=args.frequency_tolerance_hz,
            mix_index=args.mix_index,
            reference_ohms=args.reference_ohms,
            require_nonzero=args.require_nonzero,
            state_column=args.state_column,
            required_states=[_state_scalar(value) for value in args.required_state],
            csv_path=args.csv,
        )
        status["metrics"] = result
        status["status"] = "ok"
        status["return_code"] = 0
    except Exception as exc:
        status["status"] = "failed"
        status["return_code"] = 2
        status["fatal_errors"].append(f"{type(exc).__name__}: {exc}")
    if args.output:
        write_json(args.output, status)
    print_json(status)
    return int(status["return_code"])


if __name__ == "__main__":
    raise SystemExit(main())
