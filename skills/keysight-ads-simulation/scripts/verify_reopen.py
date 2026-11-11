"""Reopen an ADS workspace without force, regenerate its netlist, rerun, and compare a metric."""

from __future__ import annotations

import argparse
import os
import warnings as python_warnings
from pathlib import Path
from typing import Any

from ads_common import (
    base_status,
    print_json,
    require_new_path,
    sha256_file,
    simulator_result_evidence,
    write_json,
)
from analyze_dataset import analyze_dataset
from create_dds import inspect_data_display
from diagnose_logs import classify_text, merge_results


def _classify_saved_logs(
    directory: Path, captured_warning_texts: list[str]
) -> tuple[dict[str, Any], list[Path]]:
    logs = sorted(directory.rglob("*.ckt.out")) + sorted(directory.rglob("logFile.txt"))
    paths = list(dict.fromkeys(path.resolve() for path in logs if path.is_file()))
    parts = [
        classify_text(path.read_text(encoding="utf-8", errors="replace"), str(path))
        for path in paths
    ]
    if not paths:
        parts.append(classify_text("", str(directory / "<missing simulator log>")))
    if captured_warning_texts:
        parts.append(classify_text("\n".join(captured_warning_texts), "ADS reopen warnings"))
    return merge_results(parts), paths


def reopen_and_resimulate(
    workspace_path: str | Path,
    design_name: str,
    output_dir: str | Path,
    *,
    dataset_name: str,
    block: str,
    variable: str,
    target_frequency_hz: float | None = None,
    frequency_tolerance_hz: float = 1.0,
    mix_index: list[int] | None = None,
    reference_ohms: float = 50.0,
    baseline_dbm: float | None = None,
    db_tolerance: float = 1.0e-6,
    dds_path: str | Path | None = None,
    dds_expected_dataset: str | Path | None = None,
    dds_expected_marker: str | None = None,
) -> dict[str, Any]:
    # ADS 2026 U1 requires DDS import before Dataset in this shared process.
    import keysight.ads.dds as dds
    import keysight.ads.de as de
    from keysight.ads.de import db_uu as db
    from keysight.edatoolbox import ads

    workspace = Path(workspace_path).resolve()
    if not workspace.is_dir():
        raise FileNotFoundError(f"Workspace not found: {workspace}")
    target = require_new_path(output_dir)
    target.mkdir(parents=True)
    netlist_path = target / f"{dataset_name}_reopen.net"
    output_log = target / f"{dataset_name}_reopen.ckt.out"

    if de.workspace_is_open():
        raise RuntimeError("A workspace is already open in this Python process; refusing to close it")
    captured_warning_texts: list[str] = []
    original_cwd = Path.cwd()
    try:
        with python_warnings.catch_warnings(record=True) as captured:
            python_warnings.simplefilter("always")
            opened = de.open_workspace(workspace)
    except Exception:
        os.chdir(original_cwd)
        raise
    captured_warning_texts.extend(str(item.message) for item in captured)
    try:
        design = db.open_design(design_name)
        netlist = design.generate_netlist()
        simulator = ads.CircuitSimulator()
        simulation_result = simulator.run_netlist(
            netlist,
            output_dir=str(target),
            working_dir=str(target),
            output_file=str(output_log),
            netlist_file=str(netlist_path),
            dataset_name=dataset_name,
        )
    finally:
        try:
            opened.close()
        finally:
            os.chdir(original_cwd)

    simulation_evidence = simulator_result_evidence(
        simulation_result, none_means_check_call_success=True
    )
    if simulation_evidence["return_code"] != 0:
        raise RuntimeError(f"Reopen simulator did not return 0: {simulation_evidence}")

    diagnostics, log_paths = _classify_saved_logs(target, captured_warning_texts)
    blocking_diagnostics = (
        diagnostics["license_errors"]
        + diagnostics["fatal_errors"]
        + diagnostics["convergence_errors"]
    )

    dataset_path = target / f"{dataset_name}.ds"
    analysis = analyze_dataset(
        dataset_path,
        block=block,
        variable=variable,
        target_frequency_hz=target_frequency_hz,
        frequency_tolerance_hz=frequency_tolerance_hz,
        mix_index=mix_index,
        reference_ohms=reference_ohms,
    )
    target_metric = analysis.get("target")
    if target_metric is None:
        raise RuntimeError("Reopen analysis did not produce a target metric")
    measured_dbm = float(target_metric["power_dbm"])
    delta_db = abs(measured_dbm - baseline_dbm) if baseline_dbm is not None else None
    metric_pass = baseline_dbm is None or (delta_db is not None and delta_db <= db_tolerance)
    dds_reload = (
        inspect_data_display(
            dds_path,
            expected_dataset=dds_expected_dataset,
            expected_marker=dds_expected_marker,
        )
        if dds_path is not None
        else None
    )
    dds_reload_pass = dds_reload is None or bool(dds_reload["descriptor_reload_pass"])
    passed = bool(metric_pass and not blocking_diagnostics and dds_reload_pass)
    return {
        "workspace_reopened": True,
        "design_reopened": design_name,
        "output_dir": str(target),
        "netlist": str(netlist_path),
        "netlist_sha256": sha256_file(netlist_path),
        "output_log": str(output_log),
        "logs": [str(path) for path in log_paths],
        "dataset": str(dataset_path),
        "simulator": simulation_evidence,
        "python_warnings": captured_warning_texts,
        "diagnostics": diagnostics,
        "blocking_diagnostics": blocking_diagnostics,
        "analysis": analysis,
        "baseline_dbm": baseline_dbm,
        "measured_dbm": measured_dbm,
        "delta_db": delta_db,
        "db_tolerance": db_tolerance,
        "metric_pass": metric_pass,
        "dds_reload": dds_reload,
        "pass": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--design", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--block", required=True)
    parser.add_argument("--variable", required=True)
    parser.add_argument("--target-frequency-hz", type=float)
    parser.add_argument("--frequency-tolerance-hz", type=float, default=1.0)
    parser.add_argument("--mix-index", nargs="+", type=int)
    parser.add_argument("--reference-ohms", type=float, default=50.0)
    parser.add_argument("--baseline-dbm", type=float)
    parser.add_argument("--db-tolerance", type=float, default=1.0e-6)
    parser.add_argument("--dds", type=Path)
    parser.add_argument("--dds-expected-dataset", type=Path)
    parser.add_argument("--dds-expected-marker")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    status = base_status("verify_reopen")
    status["workspace"] = str(args.workspace.resolve())
    try:
        result = reopen_and_resimulate(
            args.workspace,
            args.design,
            args.output_dir,
            dataset_name=args.dataset_name,
            block=args.block,
            variable=args.variable,
            target_frequency_hz=args.target_frequency_hz,
            frequency_tolerance_hz=args.frequency_tolerance_hz,
            mix_index=args.mix_index,
            reference_ohms=args.reference_ohms,
            baseline_dbm=args.baseline_dbm,
            db_tolerance=args.db_tolerance,
            dds_path=args.dds,
            dds_expected_dataset=args.dds_expected_dataset,
            dds_expected_marker=args.dds_expected_marker,
        )
        status["netlist"] = result["netlist"]
        status["dataset"] = result["dataset"]
        status["metrics"] = result
        status["warnings"] = result.get("python_warnings", [])
        status["status"] = "ok" if result["pass"] else "failed"
        status["return_code"] = 0 if result["pass"] else 3
        if not result["pass"]:
            status["fatal_errors"].append("Reopened simulation metric exceeded tolerance")
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
