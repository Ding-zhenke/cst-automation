"""Run an ADS circuit netlist into a new directory and inventory its dataset."""

from __future__ import annotations

import argparse
import os
import re
import warnings as python_warnings
from pathlib import Path
from typing import Any

from ads_common import (
    base_status,
    print_json,
    require_new_path,
    simulator_result_evidence,
    write_json,
)
from analyze_dataset import analyze_dataset
from diagnose_logs import classify_text, merge_results


def validate_run_inputs(
    *,
    workspace: str | Path | None,
    design: str | None,
    netlist: str | Path | None,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Validate source selection and overwrite safety without importing ADS."""
    has_workspace_source = workspace is not None or design is not None
    has_netlist_source = netlist is not None
    if has_workspace_source and has_netlist_source:
        raise ValueError("Choose either workspace + design or netlist, not both")
    if not has_workspace_source and not has_netlist_source:
        raise ValueError("Provide workspace + design or an existing netlist")
    if has_workspace_source and (workspace is None or not str(design or "").strip()):
        raise ValueError("--workspace and --design must be supplied together")

    target = require_new_path(output_dir)
    resolved_workspace = Path(workspace).expanduser().resolve() if workspace is not None else None
    resolved_netlist = Path(netlist).expanduser().resolve() if netlist is not None else None
    if resolved_workspace is not None and not resolved_workspace.is_dir():
        raise FileNotFoundError(f"Workspace not found: {resolved_workspace}")
    if resolved_netlist is not None and not resolved_netlist.is_file():
        raise FileNotFoundError(f"Netlist not found: {resolved_netlist}")
    return {
        "workspace": resolved_workspace,
        "design": str(design).strip() if design is not None else None,
        "netlist": resolved_netlist,
        "output_dir": target,
    }


def _safe_dataset_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"ADS_{cleaned}"
    return cleaned


def _default_dataset_name(source: dict[str, Any]) -> str:
    if source["design"]:
        parts = source["design"].split(":")
        return _safe_dataset_name(parts[1] if len(parts) >= 2 else parts[0])
    return _safe_dataset_name(Path(source["netlist"]).stem)


def _collect_diagnostics(
    output_dir: Path, captured_warning_texts: list[str]
) -> tuple[dict[str, Any], list[Path]]:
    paths = sorted(output_dir.rglob("*.ckt.out")) + sorted(output_dir.rglob("logFile.txt"))
    unique = list(dict.fromkeys(path.resolve() for path in paths if path.is_file()))
    parts = [
        classify_text(path.read_text(encoding="utf-8", errors="replace"), str(path))
        for path in unique
    ]
    if not unique:
        parts.append(classify_text("", str(output_dir / "<missing simulator log>")))
    if captured_warning_texts:
        parts.append(
            classify_text("\n".join(captured_warning_texts), "ADS Design Environment warnings")
        )
    return merge_results(parts), unique


def _inventory_dataset(dataset_path: Path, requested_block: str | None) -> dict[str, Any]:
    if requested_block is not None:
        return analyze_dataset(dataset_path, block=requested_block, kind="inventory")

    # A combined DC + SP run can contain more than one block. Inventory each
    # block rather than forcing a performance-specific choice.
    import keysight.ads.dataset as dataset

    with dataset.open_dataset_for_reading(dataset_path) as opened:
        names = list(opened.keys())
    if not names:
        raise ValueError(f"Dataset contains no variable blocks: {dataset_path}")
    successful: dict[str, Any] = {}
    failures: dict[str, str] = {}
    for name in names:
        try:
            successful[name] = analyze_dataset(
                dataset_path, block=name, kind="inventory"
            )
        except Exception as exc:
            failures[name] = f"{type(exc).__name__}: {exc}"
    if not successful:
        raise ValueError(f"No dataset block contains finite numeric data: {failures}")
    return {
        "dataset": str(dataset_path),
        "blocks": names,
        "inventories": successful,
        "inventory_failures": failures,
    }


def run_circuit_simulation(
    *,
    workspace: str | Path | None,
    design: str | None,
    netlist: str | Path | None,
    output_dir: str | Path,
    dataset_name: str | None = None,
    block: str | None = None,
    mode: str = "flow",
) -> dict[str, Any]:
    source = validate_run_inputs(
        workspace=workspace,
        design=design,
        netlist=netlist,
        output_dir=output_dir,
    )
    normalized_mode = str(mode).strip().casefold()
    if normalized_mode not in ("flow", "release"):
        raise ValueError("mode must be 'flow' or 'release'")
    target: Path = source["output_dir"]
    target.mkdir(parents=True)
    selected_dataset_name = _safe_dataset_name(
        dataset_name or _default_dataset_name(source)
    )
    netlist_path = target / f"{selected_dataset_name}.net"
    simulator_netlist_path = target / f"{selected_dataset_name}_simulator_input.net"
    output_log = target / f"{selected_dataset_name}.ckt.out"
    dataset_path = target / f"{selected_dataset_name}.ds"
    status_path = target / "status.json"

    status = base_status("run_circuit_simulation")
    status.update(
        {
            "workspace": str(source["workspace"]) if source["workspace"] else None,
            "netlist": str(netlist_path),
            "dataset": str(dataset_path),
        }
    )
    status["metrics"] = {
        "mode": normalized_mode,
        "source_design": source["design"],
        "source_netlist": str(source["netlist"]) if source["netlist"] else None,
        "dataset_name": selected_dataset_name,
    }

    captured_warning_texts: list[str] = []
    opened_workspace = None
    original_cwd = Path.cwd()
    try:
        if source["workspace"] is not None:
            import keysight.ads.de as de
            from keysight.ads.de import db_uu as db

            if de.workspace_is_open():
                raise RuntimeError(
                    "A workspace is already open in this Python process; refusing to close it"
                )
            with python_warnings.catch_warnings(record=True) as captured:
                python_warnings.simplefilter("always")
                opened_workspace = de.open_workspace(source["workspace"])
            captured_warning_texts.extend(str(item.message) for item in captured)
            status["de_api_version"] = int(de.version())
            opened_design = db.open_design(source["design"])
            netlist_text = opened_design.generate_netlist()
        else:
            netlist_text = source["netlist"].read_text(encoding="utf-8", errors="strict")
        if not netlist_text.strip():
            raise ValueError("Generated/input netlist is empty")
        netlist_path.write_text(netlist_text, encoding="utf-8")

        from keysight.edatoolbox import ads

        simulation_result = ads.CircuitSimulator().run_netlist(
            netlist_text,
            output_dir=str(target),
            working_dir=str(target),
            output_file=str(output_log),
            netlist_file=str(simulator_netlist_path),
            dataset_name=selected_dataset_name,
        )
    finally:
        try:
            if opened_workspace is not None:
                opened_workspace.close()
        finally:
            os.chdir(original_cwd)

    simulator = simulator_result_evidence(
        simulation_result, none_means_check_call_success=True
    )
    diagnostics, logs = _collect_diagnostics(target, captured_warning_texts)
    blocking = (
        diagnostics["license_errors"]
        + diagnostics["fatal_errors"]
        + diagnostics["convergence_errors"]
    )
    if simulator["return_code"] != 0:
        blocking.append(
            {
                "source": "CircuitSimulator.run_netlist",
                "line": 0,
                "text": f"Simulator return code is {simulator['return_code']}",
            }
        )
    if not dataset_path.is_file() or dataset_path.stat().st_size <= 0:
        blocking.append(
            {
                "source": str(dataset_path),
                "line": 0,
                "text": "Dataset is missing or empty",
            }
        )

    inventory = None
    if not blocking:
        inventory = _inventory_dataset(dataset_path, block)
    status["metrics"].update(
        {
            "simulator": simulator,
            "diagnostics": diagnostics,
            "logs": [str(path) for path in logs],
            "dataset_inventory": inventory,
        }
    )
    status["warnings"] = (
        diagnostics["precision_warnings"]
        + diagnostics["optional_library_warnings"]
        + diagnostics["other_warnings"]
    )
    if blocking:
        status["fatal_errors"].extend(blocking)
        status["status"] = "failed"
        status["return_code"] = 3
    else:
        status["status"] = "ok"
        status["return_code"] = 0
    write_json(status_path, status)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--design")
    parser.add_argument("--netlist", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dataset-name")
    parser.add_argument("--block")
    parser.add_argument("--mode", choices=("flow", "release"), default="flow")
    return parser


def _failure_status_path(target: Path, *, existed_before: bool) -> Path:
    """Keep failure evidence out of a pre-existing output directory."""
    if not existed_before and target.is_dir():
        return target / "status.json"
    base = target.parent / f"{target.name}_failure_status.json"
    if not base.exists():
        return base
    index = 2
    while True:
        candidate = target.parent / f"{target.name}_failure_status_{index}.json"
        if not candidate.exists():
            return candidate
        index += 1


def main() -> int:
    args = build_parser().parse_args()
    target = args.output_dir.expanduser().resolve()
    existed_before = target.exists()
    try:
        status = run_circuit_simulation(
            workspace=args.workspace,
            design=args.design,
            netlist=args.netlist,
            output_dir=target,
            dataset_name=args.dataset_name,
            block=args.block,
            mode=args.mode,
        )
    except Exception as exc:
        status = base_status("run_circuit_simulation")
        status["workspace"] = str(args.workspace.resolve()) if args.workspace else None
        status["status"] = "failed"
        status["return_code"] = 2
        status["fatal_errors"].append(f"{type(exc).__name__}: {exc}")
        status["metrics"]["output_dir"] = str(target)
        status["metrics"]["output_preexisted"] = existed_before
        try:
            write_json(
                _failure_status_path(target, existed_before=existed_before),
                status,
            )
        except OSError:
            pass
    print_json(status)
    return int(status["return_code"])


if __name__ == "__main__":
    raise SystemExit(main())
