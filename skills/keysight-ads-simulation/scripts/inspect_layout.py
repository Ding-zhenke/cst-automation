from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


VALIDATION_MODES = ("flow", "release")
INSPECTION_STAGES = ("layout", "em", "fabrication")


def validate_mode(mode: str | None) -> str:
    """Validate the lightweight/strict route without importing ADS."""
    cooked = "flow" if mode is None else str(mode).strip().lower()
    if cooked not in VALIDATION_MODES:
        raise ValueError(f"mode must be one of {VALIDATION_MODES}, got {mode!r}")
    return cooked


def require_new_output(path: Path | str) -> Path:
    output = Path(path).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to replace layout inspection output: {output}")
    return output


def validate_release_evidence(payload: Any) -> dict[str, int] | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("release evidence must be a JSON object")
    result: dict[str, int] = {}
    for name in ("drc_error_count", "unrouted_count"):
        if name not in payload:
            continue
        value = payload[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        result[name] = value
    return result


def resolve_require_ports(stage: str, require_ports: bool | None) -> bool:
    cooked_stage = str(stage).strip().lower()
    if cooked_stage not in INSPECTION_STAGES:
        raise ValueError(f"stage must be one of {INSPECTION_STAGES}, got {stage!r}")
    return cooked_stage == "em" if require_ports is None else bool(require_ports)


def _safe_getattr(value: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(value, name)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return default


def _safe_list(value: Any, name: str) -> list[Any]:
    collection = _safe_getattr(value, name, ())
    if collection is None:
        return []
    try:
        return list(collection)
    except (TypeError, RuntimeError):
        return []


def _object_name(value: Any) -> str | None:
    name = _safe_getattr(value, "name")
    return None if name is None else str(name)


def _net_name(value: Any) -> str | None:
    net = _safe_getattr(value, "net")
    return _object_name(net)


def _layer_record(value: Any) -> dict[str, Any] | None:
    layer_id = _safe_getattr(value, "layer_id")
    if layer_id is None:
        layer_id = _safe_getattr(value, "layer")
    if layer_id is None:
        return None
    layer = _safe_getattr(layer_id, "layer", layer_id)
    purpose = _safe_getattr(layer_id, "purpose")
    try:
        cooked_layer: int | str = int(layer)
    except (TypeError, ValueError):
        cooked_layer = str(layer)
    return {
        "layer": cooked_layer,
        "purpose": None if purpose is None else str(purpose),
    }


def _bbox_record(value: Any) -> list[float] | None:
    bbox = _safe_getattr(value, "bbox")
    if bbox is None:
        return None
    return _box_record(bbox)


def _point_record(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(value.x), float(value.y)]
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return None


def _box_record(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(value.x1), float(value.y1), float(value.x2), float(value.y2)]
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return None


def _origin_record(value: Any) -> list[float] | None:
    origin = _safe_getattr(value, "origin")
    if origin is None:
        return None
    try:
        return [float(origin.x), float(origin.y)]
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return None


def _geometry_record(value: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": type(value).__name__,
        "net": _net_name(value),
        "bbox": _bbox_record(value),
    }
    layer = _layer_record(value)
    if layer is not None:
        record.update(layer)
    return record


def _instance_record(value: Any) -> dict[str, Any]:
    pad_via_type = _safe_getattr(value, "pad_via_type")
    padstack = _safe_getattr(value, "padstack_name")
    return {
        "name": _object_name(value),
        "type": type(value).__name__,
        "net": _net_name(value),
        "origin": _origin_record(value),
        "padstack": None if padstack is None else str(padstack),
        "pad_via_type": None if pad_via_type is None else str(pad_via_type),
    }


def _term_pins(term: Any) -> list[Any]:
    pins = _safe_getattr(term, "pins")
    if pins is not None:
        try:
            return list(pins)
        except (TypeError, RuntimeError):
            return []
    get_pins = _safe_getattr(term, "get_pins")
    if callable(get_pins):
        try:
            return list(get_pins())
        except (TypeError, RuntimeError):
            return []
    return []


def _term_record(term: Any, pins: list[Any]) -> dict[str, Any]:
    number = _safe_getattr(term, "number")
    return {
        "name": _object_name(term),
        "number": None if number is None else int(number),
        "net": _net_name(term),
        "pin_count": len(pins),
    }


def _pin_record(pin: Any, *, term: Any) -> dict[str, Any]:
    term_number = _safe_getattr(pin, "term_number")
    if term_number is None:
        term_number = _safe_getattr(term, "number")
    snap_point = _safe_getattr(pin, "snap_point")
    if snap_point is None:
        get_snap_point = _safe_getattr(pin, "get_snap_point")
        if callable(get_snap_point):
            try:
                snap_point = get_snap_point()
            except (RuntimeError, TypeError, ValueError):
                snap_point = None
    has_pinfig = bool(_safe_getattr(pin, "has_any_pinfigs", False))
    pinfig_bbox = None
    if has_pinfig:
        get_pinfig_bbox = _safe_getattr(pin, "get_pinfig_bbox")
        if callable(get_pinfig_bbox):
            try:
                pinfig_bbox = get_pinfig_bbox()
            except (RuntimeError, TypeError, ValueError):
                pinfig_bbox = None
    return {
        "name": _object_name(pin),
        "term_name": _object_name(term),
        "term_number": None if term_number is None else int(term_number),
        "net": _net_name(pin) or _net_name(term),
        "snap_point": _point_record(snap_point),
        "pinfig": {
            "has_any": has_pinfig,
            "bbox": _box_record(pinfig_bbox),
        },
    }


def inventory_design(design: Any) -> dict[str, Any]:
    """Return a JSON-safe, technology-neutral inventory of an ADS layout view."""
    shapes = [_geometry_record(value) for value in _safe_list(design, "shapes")]
    instances = [_instance_record(value) for value in _safe_list(design, "instances")]
    term_objects = _safe_list(design, "terms")
    pins_by_term = [(term, _term_pins(term)) for term in term_objects]
    terms = [_term_record(term, pins) for term, pins in pins_by_term]
    pins = [
        _pin_record(pin, term=term)
        for term, term_pins in pins_by_term
        for pin in term_pins
    ]
    nets = [
        {"name": _object_name(value)} for value in _safe_list(design, "nets")
    ]

    vias = [
        row
        for row in instances
        if "via" in row["type"].casefold()
        or "through" in str(row.get("pad_via_type", "")).casefold()
    ]
    # Physical top-level pins, flattened from design.terms, are the actual EM
    # boundary.  A term without a pin figure is not counted as a layout port.
    ports = [dict(row, source="term_pin") for row in pins]
    layer_counts = Counter(
        (str(row.get("layer")), str(row.get("purpose")))
        for row in shapes
        if "layer" in row
    )
    layers = [
        {"layer": layer, "purpose": purpose, "geometry_count": count}
        for (layer, purpose), count in sorted(layer_counts.items())
    ]
    summary = {
        "geometry_count": len(shapes),
        "instance_count": len(instances),
        "pin_count": len(pins),
        "term_count": len(terms),
        "net_count": len(nets),
        "via_count": len(vias),
        "port_count": len(ports),
        "non_empty": bool(shapes or instances or pins or terms),
    }
    return {
        "summary": summary,
        "layers": layers,
        "geometries": shapes,
        "instances": instances,
        "pins": pins,
        "terms": terms,
        "nets": nets,
        "vias": vias,
        "ports": ports,
    }


def validate_inventory(
    inventory: dict[str, Any], *, require_ports: bool, require_substrate: bool = False
) -> list[str]:
    summary = inventory.get("summary", {})
    errors: list[str] = []
    if not bool(summary.get("non_empty")):
        errors.append("layout contains no readable geometry, instances, pins, or terms")
    if require_ports and int(summary.get("port_count", 0)) <= 0:
        errors.append("EM layout requires at least one physical term pin/port")
    substrate = inventory.get("substrate", {})
    if require_substrate and substrate.get("status") != "passed":
        errors.append("EM layout requires a successfully opened ADS substrate")
    return errors


def release_design_handle(design: Any) -> None:
    close = _safe_getattr(design, "close_design")
    if callable(close):
        close()
        return
    close = _safe_getattr(design, "close")
    if callable(close):
        close()


def require_workspace_slot(de_module: Any) -> None:
    if de_module.workspace_is_open():
        raise RuntimeError(
            "refusing to inspect while an ADS workspace is already open in this process"
        )


def _substrate_inventory(
    de_module: Any, substrate_spec: str | None
) -> dict[str, Any]:
    if substrate_spec is None:
        return {
            "status": "not_applicable",
            "reason": "no substrate was requested for this inspection stage",
        }
    parts = [part.strip() for part in substrate_spec.split(":")]
    if len(parts) != 2 or not all(parts):
        raise ValueError("substrate must be written as library:name")
    from keysight.ads import subst

    library_name, substrate_name = parts
    library = de_module.Library.get(library_name)
    handle = subst.open_substrate(library, substrate_name, "r")
    try:
        return {
            "status": "passed",
            "library": library_name,
            "name": substrate_name,
            "material_count": len(list(handle.materials)),
            "conductor_layer_count": len(list(handle.layers)),
            "via_definition_count": len(list(handle.vias)),
        }
    finally:
        subst.close_substrate(library, substrate_name)


def _read_once(
    workspace_path: Path, design_name: str, substrate_spec: str | None
) -> dict[str, Any]:
    # ADS imports deliberately live below all pure input validation.
    from keysight.ads import de
    from keysight.ads.de import db_uu

    original_cwd = Path.cwd()
    require_workspace_slot(de)
    design = None
    try:
        de.open_workspace(workspace_path)
        design = db_uu.open_design(design_name, de.db.DesignMode.READ_ONLY)
        inventory = inventory_design(design)
        inventory["substrate"] = _substrate_inventory(de, substrate_spec)
        return inventory
    finally:
        if design is not None:
            release_design_handle(design)
        if de.workspace_is_open():
            de.close_workspace()
        os.chdir(original_cwd)


def _release_checks(
    mode: str, evidence: dict[str, int] | None
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    checks: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    evidence = evidence or {}
    for field in ("drc_error_count", "unrouted_count"):
        if field not in evidence:
            checks[field] = {
                "status": "not_verified",
                "verified": False,
                "source": None,
                "value": None,
            }
            if mode == "release":
                errors.append(f"release check {field} is not_verified")
            continue
        value = int(evidence[field])
        checks[field] = {
            "status": "not_verified",
            "verified": False,
            "source": "caller_asserted",
            "value": value,
        }
        if mode == "release":
            errors.append(
                f"release check {field} is caller_asserted/not_verified"
            )
    return checks, errors


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def collision_safe_path(path: Path | str) -> Path:
    """Return a new evidence path without replacing an existing file."""
    candidate = Path(path)
    if not candidate.exists():
        return candidate
    for index in range(2, 10000):
        numbered = candidate.with_name(
            f"{candidate.stem}_{index}{candidate.suffix}"
        )
        if not numbered.exists():
            return numbered
    raise RuntimeError(f"cannot allocate collision-safe failure path near {candidate}")


def inspect_layout(
    *,
    workspace: Path | str,
    design: str,
    output: Path | str,
    mode: str = "flow",
    release_evidence: dict[str, int] | None = None,
    stage: str = "layout",
    require_ports: bool | None = None,
    substrate: str | None = None,
) -> dict[str, Any]:
    mode = validate_mode(mode)
    if not isinstance(design, str) or not design.strip():
        raise ValueError("design must be a non-empty ADS lib:cell:layout name")
    evidence = validate_release_evidence(release_evidence)
    stage = str(stage).strip().lower()
    require_physical_ports = resolve_require_ports(stage, require_ports)
    workspace_path = Path(workspace).expanduser().resolve()
    output_dir = require_new_output(output)
    if not workspace_path.is_dir():
        raise FileNotFoundError(f"workspace does not exist: {workspace_path}")
    output_dir.mkdir(parents=True)

    first = _read_once(workspace_path, design, substrate)
    second = _read_once(workspace_path, design, substrate)
    require_substrate = stage == "em"
    errors = validate_inventory(
        first,
        require_ports=require_physical_ports,
        require_substrate=require_substrate,
    )
    reopen_errors = validate_inventory(
        second,
        require_ports=require_physical_ports,
        require_substrate=require_substrate,
    )
    errors.extend(f"reopened: {message}" for message in reopen_errors)
    count_fields = (
        "geometry_count",
        "instance_count",
        "pin_count",
        "term_count",
        "net_count",
        "via_count",
        "port_count",
    )
    reopen_counts_match = all(
        first["summary"][name] == second["summary"][name] for name in count_fields
    )
    if not reopen_counts_match:
        errors.append("layout inventory counts changed after close and reopen")

    flow_errors = list(errors)
    release_checks, release_errors = _release_checks(mode, evidence)
    errors.extend(release_errors)
    flow_passed = not flow_errors
    status = {
        "schema_version": 1,
        "stage": "ads_layout_inspection",
        "passed": not errors,
        "mode": mode,
        "inspection_stage": stage,
        "require_ports": require_physical_ports,
        "require_substrate": require_substrate,
        "workspace": str(workspace_path),
        "design": design,
        "output_dir": str(output_dir),
        "flow_checks": {
            "layout_opened_and_read": "passed" if first["summary"]["non_empty"] else "failed",
            "workspace_closed_and_reopened": "passed" if second["summary"]["non_empty"] else "failed",
            "reopen_counts_match": "passed" if reopen_counts_match else "failed",
            "required_ports_present": (
                "passed"
                if first["summary"]["port_count"] > 0
                else ("failed" if require_physical_ports else "not_applicable")
            ),
            "substrate": first["substrate"],
        },
        "flow_passed": flow_passed and reopen_counts_match,
        "release_passed": mode == "release" and not errors,
        "passed_scope": mode,
        "release_checks": {
            "requested": mode == "release",
            "checks": release_checks,
            "note": (
                "DRC and unrouted counts require explicit evidence; this read-only "
                "inventory does not invent unavailable results."
            ),
        },
        "inventory": first,
        "reopened_summary": second["summary"],
        "validation_errors": errors,
    }
    _write_json(output_dir / "layout_inventory.json", first)
    _write_json(output_dir / "status.json", status)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect an ADS layout database and verify a close/reopen flow."
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--design", required=True, help="ADS lib:cell:layout name")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=VALIDATION_MODES, default="flow")
    parser.add_argument("--stage", choices=INSPECTION_STAGES, default="layout")
    port_group = parser.add_mutually_exclusive_group()
    port_group.add_argument(
        "--require-ports", dest="require_ports", action="store_true"
    )
    port_group.add_argument(
        "--allow-no-ports", dest="require_ports", action="store_false"
    )
    parser.set_defaults(require_ports=None)
    parser.add_argument(
        "--substrate", help="Optional ADS substrate as library:name."
    )
    parser.add_argument(
        "--release-evidence",
        type=Path,
        help="Optional JSON containing drc_error_count and unrouted_count.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    output = Path(args.output).expanduser().resolve()
    output_preexisted = output.exists()
    try:
        evidence = None
        if args.release_evidence is not None:
            evidence = json.loads(
                args.release_evidence.read_text(encoding="utf-8")
            )
        status = inspect_layout(
            workspace=args.workspace,
            design=args.design,
            output=output,
            mode=args.mode,
            release_evidence=evidence,
            stage=args.stage,
            require_ports=args.require_ports,
            substrate=args.substrate,
        )
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["passed"] else 2
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "stage": "ads_layout_inspection",
            "passed": False,
            "mode": validate_mode(args.mode),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        try:
            if not output_preexisted and output.is_dir():
                failure_path = output / "status.json"
            else:
                failure_path = (
                    output.parent / f"{output.name}_failure_status.json"
                )
            _write_json(collision_safe_path(failure_path), failure)
        except Exception:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
