"""Create and run a parameterized two-tone diode-mixer ADS flow smoke test."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import warnings as python_warnings
from pathlib import Path
from typing import Any

from ads_common import (
    ads_version_hint,
    base_status,
    failure_status_path,
    print_json,
    require_new_path,
    sha256_file,
    simulator_result_evidence,
    write_json,
)
from analyze_dataset import analyze_dataset
from create_dds import create_data_display
from diagnose_logs import classify_text, merge_results
from verify_reopen import reopen_and_resimulate


def _safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"ADS_{cleaned}"
    return cleaned


def _set_repeated_parameter(instance, name: str, values: list[str]) -> None:
    instance.parameters[name].value = values


def _difference_mix_index(lo_frequency_hz: float, rf_frequency_hz: float) -> list[int]:
    return [-1, 1] if rf_frequency_hz > lo_frequency_hz else [1, -1]


def _metric_is_finite_nonzero(metric: dict[str, Any] | None) -> bool:
    if not metric:
        return False
    magnitude = float(metric["magnitude"])
    power_dbm = float(metric["power_dbm"])
    return math.isfinite(magnitude) and magnitude > 0 and math.isfinite(power_dbm)


def _collect_log_diagnostics(directory: Path) -> tuple[dict[str, Any], list[Path]]:
    logs = sorted(directory.rglob("*.ckt.out")) + sorted(directory.rglob("logFile.txt"))
    unique = list(dict.fromkeys(path.resolve() for path in logs if path.is_file()))
    if not unique:
        return {
            "tool": "diagnose_logs",
            "status": "failed",
            "sources": [],
            "license_errors": [],
            "fatal_errors": [
                {"source": str(directory), "line": 0, "text": "No simulator logs were saved"}
            ],
            "convergence_errors": [],
            "precision_warnings": [],
            "optional_library_warnings": [],
            "other_warnings": [],
        }, []
    results = [
        classify_text(path.read_text(encoding="utf-8", errors="replace"), str(path)) for path in unique
    ]
    return merge_results(results), unique


def _validate_inputs(args: argparse.Namespace) -> None:
    if args.lo_frequency_hz <= 0 or args.rf_frequency_hz <= 0:
        raise ValueError("LO and RF frequencies must be positive")
    if args.lo_frequency_hz == args.rf_frequency_hz:
        raise ValueError("LO and RF frequencies must differ")
    if args.lo_order < 1 or args.rf_order < 1:
        raise ValueError("Harmonic orders must be at least 1")
    if args.max_order is not None and args.max_order < 2:
        raise ValueError("MaxOrder must be at least 2 for mixing")
    if args.reference_ohms <= 0:
        raise ValueError("reference_ohms must be positive")


def run_smoke_test(args: argparse.Namespace) -> dict[str, Any]:
    _validate_inputs(args)
    # Only request DDS for explicitly selected artifacts/reopen checks. ADS
    # 2026 U1 requires it to precede Dataset when both share a process.
    dds = None
    if args.with_dds or args.with_reopen:
        import keysight.ads.dds as dds
    import keysight.ads.de as de
    from keysight.ads.de import db_uu as db
    from keysight.edatoolbox import ads

    workspace_path = require_new_path(args.workspace)
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    library_name = _safe_identifier(f"{workspace_path.stem}_lib")
    library_path = workspace_path / library_name
    design_cell = "Mixer_HB"
    design_name = f"{library_name}:{design_cell}:schematic"
    dataset_name = design_cell
    simulation_dir = workspace_path / "simulation"
    netlist_path = workspace_path / f"{design_cell}_generated.net"
    simulator_netlist_path = workspace_path / f"{design_cell}_simulator_input.net"
    output_log = simulation_dir / f"{design_cell}.ckt.out"
    max_order = args.max_order if args.max_order is not None else args.lo_order + args.rf_order
    if_frequency_hz = abs(args.rf_frequency_hz - args.lo_frequency_hz)
    if_mix_index = _difference_mix_index(args.lo_frequency_hz, args.rf_frequency_hz)

    status = base_status("mixer_smoke_test")
    status.update(
        {
            "ads_version": ads_version_hint(),
            "de_api_version": int(de.version()),
            "workspace": str(workspace_path),
            "netlist": str(netlist_path),
            "dataset": str(simulation_dir / f"{dataset_name}.ds"),
        }
    )
    if dds is not None:
        status["metrics"]["dds_api_version"] = int(dds.version())

    if de.workspace_is_open():
        raise RuntimeError(
            "A workspace is already open in this Python process; run externally or save and close it first"
        )
    original_cwd = Path.cwd()
    workspace = de.create_workspace(workspace_path)
    captured_warning_texts: list[str] = []
    try:
        with python_warnings.catch_warnings(record=True) as captured:
            python_warnings.simplefilter("always")
            workspace.open()
    except Exception:
        os.chdir(original_cwd)
        raise
    captured_warning_texts.extend(str(item.message) for item in captured)
    try:
        de.create_new_library(library_name, library_path)
        workspace.add_library(library_name, library_path, de.LibraryMode.NON_SHARED)
        design = db.create_schematic(design_name)

        lo = design.add_instance(("ads_sources", "P_1Tone", "symbol"), (-4, 1), name="LO1", angle=-90)
        lo.parameters["Num"].value = "1"
        lo.parameters["Z"].value = f"{args.reference_ohms:g} Ohm"
        lo.parameters["P"].value = f"polar(dbmtow({args.lo_power_dbm:g}),0)"
        lo.parameters["Freq"].value = f"{args.lo_frequency_hz:g} Hz"
        lo.parameters["Noise"].value = "no"

        rf = design.add_instance(("ads_sources", "P_1Tone", "symbol"), (-4, -1), name="RF1", angle=-90)
        rf.parameters["Num"].value = "2"
        rf.parameters["Z"].value = f"{args.reference_ohms:g} Ohm"
        rf.parameters["P"].value = f"polar(dbmtow({args.rf_power_dbm:g}),0)"
        rf.parameters["Freq"].value = f"{args.rf_frequency_hz:g} Hz"
        rf.parameters["Noise"].value = "no"

        diode = design.add_instance(("ads_rflib", "Diode", "symbol"), (1, -1), name="D1", angle=-90)
        diode.parameters["Model"].value = "DIODEM1"
        diode.parameters["Mode"].value = "nonlinear"
        diode.parameters["Noise"].value = "no"

        diode_model = design.add_instance(
            ("ads_rflib", "Diode_Model", "symbol"), (5, 2), name="DIODEM1", angle=0
        )
        for name, value in {
            "Is": "1e-14 A",
            "N": "1",
            "Rs": "5 Ohm",
            "Cjo": "0.2 pF",
            "Vj": "0.7 V",
            "M": "0.5",
        }.items():
            diode_model.parameters[name].value = value

        load = design.add_instance(("ads_rflib", "R", "symbol"), (3, -1), name="RLOAD", angle=-90)
        load.parameters["R"].value = f"{args.reference_ohms:g} Ohm"

        for x, y, name in [
            (-4, 0, "G_LO"),
            (-4, -2, "G_RF"),
            (1, -2, "G_DIODE"),
            (3, -2, "G_LOAD"),
        ]:
            design.add_instance(("ads_rflib", "GROUND", "symbol"), (x, y), name=name, angle=-90)

        design.add_wire([(-4.0, 1.0), (-2.0, 1.0), (-2.0, 0.0), (0.0, 0.0)])
        design.add_wire([(-4.0, -1.0), (-2.0, -1.0), (-2.0, 0.0)])
        output_wire = design.add_wire([(0.0, 0.0), (3.0, 0.0)])
        output_wire.add_wire_label("IF_OUT")
        design.add_wire([(1.0, 0.0), (1.0, -1.0)])
        design.add_wire([(3.0, 0.0), (3.0, -1.0)])

        hb = design.add_instance(
            ("ads_simulation", "HarmonicBalance", "symbol"), (5, 0), name="HB1", angle=0
        )
        _set_repeated_parameter(
            hb,
            "Freq",
            [f"{args.lo_frequency_hz:g} Hz", f"{args.rf_frequency_hz:g} Hz"],
        )
        _set_repeated_parameter(hb, "Order", [str(args.lo_order), str(args.rf_order)])
        hb.parameters["MaxOrder"].value = str(max_order)
        hb.parameters["StatusLevel"].value = "2"

        design.save_design()
        netlist = design.generate_netlist()
        netlist_path.write_text(netlist, encoding="utf-8")
        simulation_dir.mkdir(parents=True)
        simulation_result = ads.CircuitSimulator().run_netlist(
            netlist,
            output_dir=str(simulation_dir),
            working_dir=str(simulation_dir),
            output_file=str(output_log),
            netlist_file=str(simulator_netlist_path),
            dataset_name=dataset_name,
        )
    finally:
        try:
            workspace.close()
        finally:
            os.chdir(original_cwd)

    simulation_evidence = simulator_result_evidence(
        simulation_result, none_means_check_call_success=True
    )
    if simulation_evidence["return_code"] != 0:
        raise RuntimeError(f"Simulator did not return 0: {simulation_evidence}")

    dataset_path = simulation_dir / f"{dataset_name}.ds"
    spectrum_csv = (
        workspace_path / f"{dataset_name}_spectrum.csv" if args.with_report else None
    )
    if_result = analyze_dataset(
        dataset_path,
        block="HB1.HB",
        variable="IF_OUT",
        mix_index=if_mix_index,
        reference_ohms=args.reference_ohms,
        require_nonzero=True,
        csv_path=spectrum_csv,
    )
    lo_result = analyze_dataset(
        dataset_path,
        block="HB1.HB",
        variable="IF_OUT",
        mix_index=[1, 0],
        reference_ohms=args.reference_ohms,
    )
    rf_result = analyze_dataset(
        dataset_path,
        block="HB1.HB",
        variable="IF_OUT",
        mix_index=[0, 1],
        reference_ohms=args.reference_ohms,
    )
    sum_result = analyze_dataset(
        dataset_path,
        block="HB1.HB",
        variable="IF_OUT",
        mix_index=[1, 1],
        reference_ohms=args.reference_ohms,
    )

    if_metric = if_result["target"]
    if if_metric is None:
        raise RuntimeError("100 MHz difference-frequency metric is missing")
    frequency_error_hz = abs(float(if_metric["frequency_hz"]) - if_frequency_hz)
    if frequency_error_hz > args.frequency_tolerance_hz or float(if_metric["magnitude"]) <= 0:
        raise RuntimeError(
            f"Difference-frequency acceptance failed: error={frequency_error_hz} Hz, "
            f"magnitude={if_metric['magnitude']}"
        )

    initial_diagnostics, initial_log_paths = _collect_log_diagnostics(simulation_dir)
    if captured_warning_texts:
        initial_diagnostics = merge_results(
            [
                initial_diagnostics,
                classify_text(
                    "\n".join(captured_warning_texts), "ADS initial Design Environment warnings"
                ),
            ]
        )
    initial_blocking_diagnostics = (
        initial_diagnostics["license_errors"]
        + initial_diagnostics["fatal_errors"]
        + initial_diagnostics["convergence_errors"]
    )
    if initial_blocking_diagnostics:
        raise RuntimeError(f"Blocking simulator diagnostics: {initial_blocking_diagnostics}")
    combined_log = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in initial_log_paths
    )
    two_tone_confirmed = bool(re.search(r"Number of tones:\s*2\.", combined_log))

    dds_path = workspace_path / f"{dataset_name}.dds"
    png_path = workspace_path / f"{dataset_name}_spectrum.png"
    pdf_path = workspace_path / f"{dataset_name}_spectrum.pdf"
    dds_result = None
    if args.with_dds:
        dds_result = create_data_display(
            dataset_path,
            dds_path,
            trace_expression=f"dbm(IF_OUT,{args.reference_ohms:g})",
            title="Two-Tone Diode Mixer: IF_OUT Spectrum",
            marker_name="mIF",
            marker_value=f"{if_frequency_hz:g} Hz",
            equation=(
                f"P_IF_dBm=dbm(mix(IF_OUT,{{{if_mix_index[0]},{if_mix_index[1]}}}),"
                f"{args.reference_ohms:g})"
            ),
            note=(
                f"Expected IF = RF - LO = {args.rf_frequency_hz:g} - "
                f"{args.lo_frequency_hz:g} = {if_frequency_hz:g} Hz"
            ),
            png_path=png_path,
            pdf_path=pdf_path,
        )

    reopen = None
    if args.with_reopen:
        reopen = reopen_and_resimulate(
            workspace_path,
            design_name,
            workspace_path / "reopen_simulation",
            dataset_name=dataset_name,
            block="HB1.HB",
            variable="IF_OUT",
            mix_index=if_mix_index,
            reference_ohms=args.reference_ohms,
            baseline_dbm=float(if_metric["power_dbm"]),
            db_tolerance=args.reopen_tolerance_db,
            dds_path=dds_path if args.with_dds else None,
            dds_expected_dataset=dataset_path if args.with_dds else None,
            dds_expected_marker="mIF" if args.with_dds else None,
        )

    diagnostics = (
        merge_results([initial_diagnostics, reopen["diagnostics"]])
        if reopen is not None
        else initial_diagnostics
    )
    log_paths = initial_log_paths + (
        [Path(path) for path in reopen["logs"]] if reopen is not None else []
    )
    blocking_diagnostics = (
        diagnostics["license_errors"]
        + diagnostics["fatal_errors"]
        + diagnostics["convergence_errors"]
    )
    precision_warnings = diagnostics["precision_warnings"]
    optional_warnings = diagnostics["optional_library_warnings"]
    other_warnings = diagnostics["other_warnings"]
    status["warnings"] = precision_warnings + optional_warnings + other_warnings
    if not two_tone_confirmed:
        status["warnings"].append(
            "Saved logs do not contain an explicit two-tone count line"
        )

    other_spectrum_pass = any(
        _metric_is_finite_nonzero(metric)
        for metric in (lo_result["target"], rf_result["target"], sum_result["target"])
    )
    flow_pass = bool(
        frequency_error_hz <= args.frequency_tolerance_hz
        and _metric_is_finite_nonzero(if_metric)
        and simulation_evidence["return_code"] == 0
        and dataset_path.is_file()
        and dataset_path.stat().st_size > 0
        and not blocking_diagnostics
    )
    dds_pass = not args.with_dds or all(
        path.is_file() and path.stat().st_size > 0
        for path in (dds_path, png_path, pdf_path)
    )
    reopen_pass = not args.with_reopen or bool(reopen and reopen["pass"])
    preliminary_pass = bool(flow_pass and dds_pass and reopen_pass)

    report_path = workspace_path / "ADS_Mixer_SmokeTest_Report_zh.md"
    if args.with_report:
        report_path.write_text(
            "\n".join(
                [
                    "# ADS 二极管混频器流程验证报告",
                    "",
                    f"- ADS：{status['ads_version']}；DE API：{status['de_api_version']}",
                    (
                        f"- LO：{args.lo_frequency_hz / 1e9:g} GHz / "
                        f"{args.lo_power_dbm:g} dBm / {args.lo_order} 阶"
                    ),
                    (
                        f"- RF：{args.rf_frequency_hz / 1e9:g} GHz / "
                        f"{args.rf_power_dbm:g} dBm / {args.rf_order} 阶"
                    ),
                    (
                        f"- 差频：{float(if_metric['frequency_hz']) / 1e6:g} MHz；"
                        f"{float(if_metric['power_dbm']):.6f} dBm（{args.reference_ohms:g} Ω）"
                    ),
                    (
                        f"- HB 数据点：{if_result['row_count']}；"
                        f"日志明确记录双基频：{'是' if two_tone_confirmed else '否'}"
                    ),
                    f"- 阻断性诊断：{len(blocking_diagnostics)}",
                    f"- 默认 flow 验证：{'通过' if preliminary_pass else '失败'}",
                    (
                        f"- DDS：{'已生成' if args.with_dds else '未请求'}；"
                        f"重开复算：{'已执行' if args.with_reopen else '未请求'}"
                    ),
                    "- GUI 检查：不适用（本次未请求 GUI 验证）",
                    "",
                    "> 此报告只证明设计构建、HB 求解和数据读取流程可运行，不声明转换增益、隔离或杂散性能达标。",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    report_pass = not args.with_report or (
        report_path.is_file() and report_path.stat().st_size > 0
    )
    overall_pass = bool(preliminary_pass and report_pass)

    status["metrics"] = {
        "configuration": {
            "lo_frequency_hz": args.lo_frequency_hz,
            "lo_power_dbm": args.lo_power_dbm,
            "rf_frequency_hz": args.rf_frequency_hz,
            "rf_power_dbm": args.rf_power_dbm,
            "lo_order": args.lo_order,
            "rf_order": args.rf_order,
            "max_order": max_order,
            "reference_ohms": args.reference_ohms,
            "if_frequency_hz": if_frequency_hz,
            "if_mix_index": if_mix_index,
        },
        "requested_artifacts": {
            "dds": args.with_dds,
            "reopen": args.with_reopen,
            "report": args.with_report,
        },
        "de_product_version": str(de.product_version()),
        "dds_api_version": int(dds.version()) if dds is not None else None,
        "simulator": simulation_evidence,
        "dataset_block": "HB1.HB",
        "spectral_points": if_result["row_count"],
        "hb_two_tone_confirmed": two_tone_confirmed,
        "if_difference": if_metric,
        "if_frequency_error_hz": frequency_error_hz,
        "lo_output": lo_result["target"],
        "rf_output": rf_result["target"],
        "sum_output": sum_result["target"],
        "other_spectrum_component_present": other_spectrum_pass,
        "diagnostics": diagnostics,
        "logs": [str(path) for path in log_paths],
        "netlist_sha256": sha256_file(netlist_path),
        "spectrum_csv": str(spectrum_csv) if spectrum_csv is not None else None,
        "data_display": dds_result,
        "reopen_verification": reopen,
        "report": str(report_path) if args.with_report else None,
        "flow_pass": flow_pass,
        "optional_dds_pass": dds_pass,
        "optional_reopen_pass": reopen_pass,
        "optional_report_pass": report_pass,
        "visible_window_verified": False,
        "visible_window_verification": "not_applicable",
        "overall_acceptance_pass": overall_pass,
    }
    status["status"] = "ok" if overall_pass else "failed"
    status["return_code"] = 0 if overall_pass else 3
    if not overall_pass:
        status["fatal_errors"].append(
            "Requested mixer flow stages did not all complete successfully"
        )
    write_json(workspace_path / "verification_result.json", status)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--lo-frequency-hz", type=float, default=1.0e9)
    parser.add_argument("--rf-frequency-hz", type=float, default=1.1e9)
    parser.add_argument("--lo-power-dbm", type=float, default=10.0)
    parser.add_argument("--rf-power-dbm", type=float, default=-20.0)
    parser.add_argument("--lo-order", type=int, default=7)
    parser.add_argument("--rf-order", type=int, default=3)
    parser.add_argument("--max-order", type=int)
    parser.add_argument("--reference-ohms", type=float, default=50.0)
    parser.add_argument("--frequency-tolerance-hz", type=float, default=1.0)
    parser.add_argument("--reopen-tolerance-db", type=float, default=1.0e-6)
    parser.add_argument(
        "--with-dds",
        action="store_true",
        help="Generate DDS plus headless PNG/PDF artifacts",
    )
    parser.add_argument(
        "--with-reopen",
        action="store_true",
        help="Reopen the workspace and rerun the generated design",
    )
    parser.add_argument(
        "--with-report",
        action="store_true",
        help="Generate a Chinese Markdown flow report and spectrum CSV",
    )
    parser.add_argument("--status-output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    existed_before = args.workspace.exists()
    try:
        status = run_smoke_test(args)
    except Exception as exc:
        status = base_status("mixer_smoke_test")
        status["ads_version"] = ads_version_hint()
        status["workspace"] = str(args.workspace.resolve())
        status["status"] = "failed"
        status["return_code"] = 2
        status["fatal_errors"].append(f"{type(exc).__name__}: {exc}")
        failure_path = failure_status_path(args.workspace, existed_before=existed_before)
        try:
            write_json(failure_path, status)
        except OSError:
            pass
    if args.status_output:
        write_json(args.status_output, status)
    print_json(status)
    return int(status["return_code"])


if __name__ == "__main__":
    raise SystemExit(main())
