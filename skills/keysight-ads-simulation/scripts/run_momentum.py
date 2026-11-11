from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable


VALIDATION_MODES = ("flow", "release")
MOMENTUM_SIMULATOR = "com.keysight.xxpro.simulator.momentum"
REQUIRED_KEYS = ("workspace", "output_dir", "preset", "frequency", "ports")
SUCCESS_TERMINAL_STATUSES = frozenset({"Completed", "Solved"})
FAILURE_TERMINAL_STATUSES = frozenset({"Error", "Killed", "Unknown"})


def is_successful_terminal_status(status: Any) -> bool:
    return str(status) in SUCCESS_TERMINAL_STATUSES


def is_terminal_status(status: Any) -> bool:
    return str(status) in SUCCESS_TERMINAL_STATUSES | FAILURE_TERMINAL_STATUSES


def _name_tuple(value: Any, size: int, label: str) -> tuple[str, ...]:
    try:
        result = tuple(str(item) for item in value)
    except TypeError as exc:
        raise ValueError(f"{label} is not a name tuple: {value!r}") from exc
    if len(result) != size or not all(result):
        raise ValueError(f"{label} must contain {size} non-empty names, got {result!r}")
    return result


def validate_rfpro_design_refs(
    design_refs: Any,
    *,
    expected_layout: tuple[str, str, str],
    expected_substrate: tuple[str, str] | None,
) -> dict[str, Any]:
    """Verify that an existing RFPro view is bound to the requested sources."""
    if not isinstance(design_refs, dict) or len(design_refs) != 1:
        raise RuntimeError(
            f"RFPro setup must contain exactly one design reference, got {design_refs!r}"
        )
    reference = next(iter(design_refs.values()))
    actual_layout = _name_tuple(
        getattr(reference, "layout", None), 3, "RFPro layout reference"
    )
    actual_substrate = _name_tuple(
        getattr(reference, "substrate", None), 2, "RFPro substrate reference"
    )
    if actual_layout != tuple(expected_layout):
        raise RuntimeError(
            f"RFPro source layout mismatch: actual={actual_layout}, "
            f"expected={tuple(expected_layout)}"
        )
    if expected_substrate is not None and actual_substrate != tuple(expected_substrate):
        raise RuntimeError(
            f"RFPro substrate mismatch: actual={actual_substrate}, "
            f"expected={tuple(expected_substrate)}"
        )
    return {
        "layout": list(actual_layout),
        "substrate": list(actual_substrate),
        "verified": True,
        "source": "emtools.EmproSetup.design_refs",
    }


def validate_port_assignments(
    planned: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    actual_by_name = {str(item.get("name")): item for item in actual}
    if len(actual_by_name) != len(actual):
        errors.append("created Momentum port names are not unique")
    if set(actual_by_name) != {str(item["name"]) for item in planned}:
        errors.append("created Momentum port name set differs from the run plan")
    for plan in planned:
        name = str(plan["name"])
        item = actual_by_name.get(name)
        if item is None:
            continue
        if list(item.get("plus_pins", ())) != [str(plan["plus_pin"])]:
            errors.append(f"port {name} plus-pin mapping differs from the run plan")
        if list(item.get("minus_pins", ())) != [str(plan["minus_pin"])]:
            errors.append(f"port {name} minus-pin mapping differs from the run plan")
        try:
            impedance = float(item.get("reference_impedance_ohm"))
        except (TypeError, ValueError):
            impedance = math.nan
        if not math.isclose(
            impedance,
            float(plan["reference_impedance_ohm"]),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            errors.append(f"port {name} reference impedance differs from the run plan")
        if canonical_feed_type(item.get("feed_type")) != canonical_feed_type(
            plan["feed_type"]
        ):
            errors.append(f"port {name} feed type differs from the run plan")
    return errors


def canonical_feed_type(value: Any) -> str:
    """Normalize the local RFPro SMD/ClosedLoop naming without guessing others."""
    raw = str(value).strip()
    token = raw.casefold().rsplit(".", 1)[-1]
    compact = token.replace("_", "").replace("-", "").replace(" ", "")
    if compact in {"smd", "closedloop"}:
        return "closed_loop"
    if compact == "auto":
        return "auto"
    return raw


def release_mesh_check(release_evidence: dict[str, Any]) -> dict[str, Any]:
    raw = release_evidence.get("mesh_convergence")
    return {
        "status": "not_verified",
        "verified": False,
        "source": "caller_asserted" if raw is not None else None,
        "caller_value": raw,
    }


def validate_mode(mode: str | None) -> str:
    cooked = "flow" if mode is None else str(mode).strip().lower()
    if cooked not in VALIDATION_MODES:
        raise ValueError(f"mode must be one of {VALIDATION_MODES}, got {mode!r}")
    return cooked


def parse_design(config: dict[str, Any]) -> tuple[str, str, str]:
    """Return (library, cell, layout view) from either supported config form."""
    design = config.get("design")
    explicit = any(key in config for key in ("library", "cell", "view"))
    if design is not None:
        if not isinstance(design, str) or not design.strip():
            raise ValueError("design must be a non-empty lib:cell:view string")
        parts = [part.strip() for part in design.split(":")]
        if len(parts) != 3 or not all(parts):
            raise ValueError("design must have exactly lib:cell:view components")
        if explicit:
            expected = (
                str(config.get("library", parts[0])).strip(),
                str(config.get("cell", parts[1])).strip(),
                str(config.get("view", parts[2])).strip(),
            )
            if tuple(parts) != expected:
                raise ValueError("design and library/cell/view select different layouts")
        return parts[0], parts[1], parts[2]
    library = config.get("library")
    cell = config.get("cell")
    view = config.get("view", "layout")
    if not all(isinstance(value, str) and value.strip() for value in (library, cell, view)):
        raise ValueError("provide design or non-empty library, cell, and optional view")
    return str(library).strip(), str(cell).strip(), str(view).strip()


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    cooked = float(value)
    if not math.isfinite(cooked):
        raise ValueError(f"{name} must be a finite number")
    return cooked


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Pure-Python schema validation; no ADS or EM module is imported here."""
    if not isinstance(config, dict):
        raise ValueError("Momentum configuration must be a JSON object")
    missing = [name for name in REQUIRED_KEYS if name not in config]
    if missing:
        raise ValueError(f"missing Momentum config keys: {missing}")
    for name in ("workspace", "output_dir", "preset"):
        if not isinstance(config[name], str) or not config[name].strip():
            raise ValueError(f"{name} must be a non-empty string")
    parse_design(config)
    validate_mode(config.get("mode", "flow"))

    frequency = config["frequency"]
    if not isinstance(frequency, dict):
        raise ValueError("frequency must be an object")
    missing_frequency = [
        name for name in ("start_hz", "stop_hz", "points") if name not in frequency
    ]
    if missing_frequency:
        raise ValueError(f"missing frequency keys: {missing_frequency}")
    start_hz = _finite_number(frequency["start_hz"], "frequency.start_hz")
    stop_hz = _finite_number(frequency["stop_hz"], "frequency.stop_hz")
    if start_hz < 0.0 or stop_hz <= start_hz:
        raise ValueError("frequency requires 0 <= start_hz < stop_hz")
    points = frequency["points"]
    if isinstance(points, bool) or not isinstance(points, int) or points < 2:
        raise ValueError("frequency.points must be an integer >= 2")

    ports = config["ports"]
    if not isinstance(ports, list) or not ports:
        raise ValueError("ports must be a non-empty list")
    names: set[str] = set()
    for index, port in enumerate(ports):
        if not isinstance(port, dict):
            raise ValueError(f"ports[{index}] must be an object")
        missing_port = [
            name
            for name in (
                "name",
                "plus_pin",
                "minus_pin",
                "reference_impedance_ohm",
            )
            if name not in port
        ]
        if missing_port:
            raise ValueError(f"ports[{index}] missing keys: {missing_port}")
        for name in ("name", "plus_pin", "minus_pin"):
            if not isinstance(port[name], str) or not port[name].strip():
                raise ValueError(f"ports[{index}].{name} must be a non-empty string")
        port_name = port["name"].strip()
        if port_name in names:
            raise ValueError(f"duplicate Momentum port name: {port_name}")
        names.add(port_name)
        if port["plus_pin"].strip() == port["minus_pin"].strip():
            raise ValueError(f"ports[{index}] plus_pin and minus_pin must differ")
        impedance = _finite_number(
            port["reference_impedance_ohm"],
            f"ports[{index}].reference_impedance_ohm",
        )
        if impedance <= 0.0:
            raise ValueError(f"ports[{index}] reference impedance must be positive")
        feed_type = port.get("feed_type", "SMD")
        if not isinstance(feed_type, str) or not feed_type.strip():
            raise ValueError(f"ports[{index}].feed_type must be a non-empty string")

    output = Path(config["output_dir"]).expanduser()
    if output.exists():
        raise FileExistsError(f"refusing to replace Momentum output: {output.resolve()}")
    substrate = config.get("substrate")
    if substrate is not None:
        _parse_substrate(substrate, parse_design(config)[0])
    evidence = config.get("release_evidence")
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("release_evidence must be an object when provided")
    return config


def resolve_config_paths(
    config: dict[str, Any], config_path: Path | str
) -> dict[str, Any]:
    base = Path(config_path).resolve().parent
    resolved = dict(config)
    for name in ("workspace", "output_dir"):
        raw = resolved.get(name)
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = base / path
        resolved[name] = str(path.resolve())
    resolved["mode"] = validate_mode(resolved.get("mode", "flow"))
    return resolved


def _parse_substrate(value: Any, default_library: str) -> tuple[str, str]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(":")]
        if len(parts) == 1 and parts[0]:
            return default_library, parts[0]
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1]
    elif isinstance(value, dict):
        library = value.get("library", default_library)
        name = value.get("name")
        if all(isinstance(item, str) and item.strip() for item in (library, name)):
            return str(library).strip(), str(name).strip()
    raise ValueError("substrate must be 'library:name', 'name', or {library,name}")


def _hz_expression(value: float) -> str:
    if math.isclose(value % 1e9, 0.0, abs_tol=1e-6):
        return f"{value / 1e9:g} GHz"
    if math.isclose(value % 1e6, 0.0, abs_tol=1e-6):
        return f"{value / 1e6:g} MHz"
    if math.isclose(value % 1e3, 0.0, abs_tol=1e-6):
        return f"{value / 1e3:g} kHz"
    return f"{value:g} Hz"


def build_run_plan(config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    library, cell, layout_view = parse_design(config)
    frequency = config["frequency"]
    ports = [
        {
            "name": str(port["name"]).strip(),
            "plus_pin": str(port["plus_pin"]).strip(),
            "minus_pin": str(port["minus_pin"]).strip(),
            "reference_impedance_ohm": float(port["reference_impedance_ohm"]),
            "feed_type": str(port.get("feed_type", "SMD")).strip(),
        }
        for port in config["ports"]
    ]
    substrate = config.get("substrate")
    substrate_pair = (
        list(_parse_substrate(substrate, library)) if substrate is not None else None
    )
    mesh = config.get("mesh") or {}
    if not isinstance(mesh, dict):
        raise ValueError("mesh must be an object when provided")
    return {
        "schema_version": 1,
        "analysis_type": "EMFU",
        "analysis_name": str(config.get("analysis_name", "ADS_Momentum_Flow")),
        "simulator": str(config.get("simulator", MOMENTUM_SIMULATOR)),
        "preset": str(config["preset"]),
        "workspace": str(Path(config["workspace"]).resolve()),
        "output_dir": str(Path(config["output_dir"]).resolve()),
        "layout_lcv": [library, cell, layout_view],
        "rfpro_view": str(config.get("rfpro_view", "rfpro")),
        "substrate": substrate_pair,
        "frequency_plan": {
            "compute_type": "Simulated",
            "sweep_type": str(frequency.get("sweep_type", "Linear")),
            "start_hz": float(frequency["start_hz"]),
            "stop_hz": float(frequency["stop_hz"]),
            "points": int(frequency["points"]),
            "sample_points_limit": int(frequency.get("sample_points_limit", 120)),
            "points_per_decade": int(frequency.get("points_per_decade", 20)),
        },
        "ports": ports,
        "mesh": mesh,
        "reuse_existing": bool(config.get("reuse_existing", False)),
        "mode": validate_mode(config.get("mode", "flow")),
        "release_evidence": dict(config.get("release_evidence") or {}),
    }


def ads_create_or_verify_rfpro_view(
    workspace_path: str,
    layout_lcv: list[str],
    rfpro_view: str,
    substrate: list[str] | None,
) -> dict[str, Any]:
    """Run inside an ADS Python context and ensure an RFPro view is available."""
    from keysight.ads import de
    import keysight.ads.emtools as emtools

    library_name, cell_name, layout_view = layout_lcv
    workspace = de.open_workspace(Path(workspace_path))
    try:
        library = de.Library.get(library_name)
        cell = library.cell(cell_name)
        if not cell.view_exists(layout_view):
            raise RuntimeError(
                f"layout view does not exist: {library_name}:{cell_name}:{layout_view}"
            )
        created = False
        substrate_pair = tuple(substrate) if substrate is not None else None
        if not cell.view_exists(rfpro_view):
            if substrate_pair is None:
                emsetup = emtools.find_emsetup_view_name(
                    (library_name, cell_name, layout_view)
                )
                if emsetup and cell.view_exists(emsetup):
                    substrate_pair = tuple(
                        emtools.get_substrate_info(
                            (library_name, cell_name, emsetup)
                        )
                    )
            if substrate_pair is None:
                raise RuntimeError(
                    "RFPro view is absent and no substrate was provided or discoverable"
                )
            emtools.create_empro_view(
                (library_name, cell_name, rfpro_view),
                "rfpro",
                (library_name, cell_name, layout_view),
                substrate_pair,
            )
            created = True
        if not cell.view_exists(rfpro_view):
            raise RuntimeError("RFPro view creation did not persist")
        setup = emtools.EmproSetup((library_name, cell_name, rfpro_view))
        binding = validate_rfpro_design_refs(
            setup.design_refs,
            expected_layout=(library_name, cell_name, layout_view),
            expected_substrate=substrate_pair,
        )
        return {
            "layout_lcv": list(layout_lcv),
            "rfpro_lcv": [library_name, cell_name, rfpro_view],
            "substrate": binding["substrate"],
            "source_binding": binding,
            "created": created,
            "verified": True,
        }
    finally:
        workspace.close()


def _simulation_files(root: Path, pattern: str) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (
            path
            for path in root.rglob(pattern)
            if path.is_file() and path.stat().st_size > 0
        ),
        key=lambda path: (path.stat().st_mtime_ns, str(path)),
    )


def xxpro_run_momentum(
    workspace_path: str,
    plan: dict[str, Any],
    output_dir: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run inside an XXPro context using the verified RFPro/Momentum sequence."""
    import empro
    import empro.enparams
    import empro.toolkit.analysis as analysis_toolkit
    import keysight.edatoolbox.ads as ads
    import keysight.edatoolbox.xxpro as xxpro

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    library, cell, _layout_view = plan["layout_lcv"]
    xxpro.use_workspace(workspace_path)
    xxpro.load_pro_view(
        ads.LibraryCellView(
            library=library, cell=cell, view=plan["rfpro_view"]
        )
    )
    project = empro.activeProject
    if project is None:
        raise RuntimeError("RFPro did not create an active project")

    analysis_name = f"{plan['analysis_name']}_{time.strftime('%Y%m%dT%H%M%S')}"
    analysis = empro.analysis.Analysis(
        empro.analysis.Analysis.EMFUAnalysisType, analysis_name
    )
    options = analysis.simulationSettings
    try:
        options.setPresetByName(plan["preset"])
    except Exception as exc:
        raise ValueError(
            f"Momentum preset {plan['preset']!r} is unavailable in this RFPro "
            "installation; use the exact local preset name, for example "
            "'Momentum Microwave'."
        ) from exc
    options.simulator = plan["simulator"]
    options.sParametersEnabled = True

    frequency_plans = options.femFrequencyPlanList()
    frequency_plans.clear()
    frequency_plans._frequencyPlanType = "NoInterpolating_NoFields"
    sweep = plan["frequency_plan"]
    frequency_plan = empro.simulation.FrequencyPlan()
    frequency_plan.computeType = sweep["compute_type"]
    frequency_plan.sweepType = sweep["sweep_type"]
    frequency_plan.startFrequency = _hz_expression(float(sweep["start_hz"]))
    frequency_plan.stopFrequency = _hz_expression(float(sweep["stop_hz"]))
    frequency_plan.numberOfFrequencyPoints = int(sweep["points"])
    frequency_plan.samplePointsLimit = int(sweep["sample_points_limit"])
    frequency_plan.pointsPerDecade = int(sweep["points_per_decade"])
    frequency_plan.enabled = True
    frequency_plans.append(frequency_plan)

    mesh = options.momMeshSettings
    mesh_config = plan.get("mesh") or {}
    mesh_attributes = {
        "generation": "generation",
        "mesh_granularity": "meshGranularity",
        "mesh_reduction": "meshReduction",
        "edge_mesh": "edgeMesh",
        "use_mesh_domain_optimization": "useMeshDomainOptimization",
    }
    for config_name, attribute_name in mesh_attributes.items():
        if config_name in mesh_config:
            setattr(mesh, attribute_name, mesh_config[config_name])

    pin_index: dict[str, Any] = {}
    for owner in list(project.geometry):
        for index in range(owner._pinCount()):
            pin = owner._pin(index)
            name = str(pin.name)
            if name in pin_index:
                raise RuntimeError(f"RFPro physical pin name is not unique: {name}")
            pin_index[name] = pin
    required_pin_names = {
        str(port[key]) for port in plan["ports"] for key in ("plus_pin", "minus_pin")
    }
    missing_pin_names = sorted(required_pin_names - set(pin_index))
    if missing_pin_names:
        raise RuntimeError(
            f"RFPro physical pins required by the port plan are missing: {missing_pin_names}; "
            f"available={sorted(pin_index)}"
        )

    for port_plan in plan["ports"]:
        port = analysis_toolkit.createPortFromPins(
            [pin_index[port_plan["plus_pin"]]],
            [pin_index[port_plan["minus_pin"]]],
            name=port_plan["name"],
        )
        port.referenceImpedance = str(port_plan["reference_impedance_ohm"])
        port.feedType = port_plan["feed_type"]
        analysis.ports.append(port)
    port_names = [str(port.name) for port in analysis.ports]
    port_assignments = [
        {
            "name": str(port.name),
            "plus_pins": [str(pin.name) for pin in port.plusPins()],
            "minus_pins": [str(pin.name) for pin in port.minusPins()],
            "reference_impedance_ohm": float(str(port.referenceImpedance)),
            "feed_type": str(port.feedType),
        }
        for port in analysis.ports
    ]
    assignment_errors = validate_port_assignments(plan["ports"], port_assignments)
    if assignment_errors:
        raise RuntimeError("; ".join(assignment_errors))

    with project:
        analysis_index = project.analyses.append(analysis)
        project.saveActiveProject()
    active_analysis = project.analyses[analysis_index]

    update_deadline = time.time() + min(60.0, timeout_seconds)
    stable_valid_since: float | None = None
    while stable_valid_since is None or time.time() - stable_valid_since < 1.0:
        empro.gui.processEvents()
        if project.isValid():
            if stable_valid_since is None:
                stable_valid_since = time.time()
        else:
            stable_valid_since = None
            reason = str(project.reasonWhyInvalid())
            if "update" not in reason.casefold() or "progress" not in reason.casefold():
                raise RuntimeError(f"RFPro project is invalid: {reason}")
        if time.time() >= update_deadline:
            raise TimeoutError("RFPro project update did not reach stable validity")
        time.sleep(0.1)

    start_time = time.time()
    analysis_toolkit.runAnalysis(
        active_analysis,
        waitForConfirmation=False,
        saveProject=False,
        reuseExistingIfPossible=bool(plan["reuse_existing"]),
    )
    simulation = active_analysis.simulation()
    if simulation is None and len(project.simulations):
        simulation = project.simulations[-1]
    if simulation is None:
        raise RuntimeError("Momentum did not create a simulation object")
    ready_deadline = start_time + min(30.0, max(1.0, timeout_seconds / 4.0))
    while not is_terminal_status(simulation.status):
        if str(simulation.status) == "Ready" and time.time() > ready_deadline:
            raise RuntimeError(
                "Momentum remained Ready after runAnalysis; no solve was started"
            )
        if time.time() - start_time > timeout_seconds:
            simulation.kill()
            raise TimeoutError(
                f"Momentum exceeded timeout of {timeout_seconds:g} seconds"
            )
        time.sleep(0.2)
        empro.gui.processEvents()

    simulation_status = str(simulation.status)
    simulation_path = Path(str(simulation.simulationPath())).resolve()
    log_file = output_path / "momentum_simulation.log"
    log_file.write_text(
        str(simulation.output(True)), encoding="utf-8", errors="replace"
    )
    sio_files = _simulation_files(simulation_path, "*.sio")
    dataset_files: list[Path] = []
    conversion: dict[str, Any] = {"attempted": False, "converted": False}
    if is_successful_terminal_status(simulation_status) and sio_files:
        preferred = next(
            (
                path
                for path in reversed(sio_files)
                if path.name == "proj.sio" and path.parent.name == "work"
            ),
            sio_files[-1],
        )
        dataset_path = output_path / "momentum.ds"
        conversion = {
            "attempted": True,
            "source_sio": str(preferred),
            "target_dataset": str(dataset_path),
            "converted": False,
        }
        try:
            converted = bool(
                empro.enparams._sio2adsds_discrete(
                    str(preferred), str(dataset_path)
                )
            )
            conversion["converted"] = converted
            if converted and dataset_path.is_file() and dataset_path.stat().st_size > 0:
                dataset_files.append(dataset_path)
        except Exception as exc:
            conversion["error"] = f"{type(exc).__name__}: {exc}"

    return {
        "analysis_name": analysis_name,
        "simulator": str(options.simulator),
        "preset": str(options.preset.name) if options.preset else None,
        "ports": port_names,
        "physical_pin_names": sorted(pin_index),
        "port_assignments": port_assignments,
        "port_assignments_verified": True,
        "simulation_status": simulation_status,
        "simulation_path": str(simulation_path),
        "elapsed_seconds": time.time() - start_time,
        "log_file": str(log_file),
        "sio_files": [str(path) for path in sio_files],
        "dataset_files": [str(path) for path in dataset_files],
        "dataset_conversion": conversion,
    }


def validate_run_result(
    result: dict[str, Any], *, mode: str, release_evidence: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not is_successful_terminal_status(result.get("simulation_status")):
        errors.append(
            "Momentum simulation status must be Completed or Solved, got "
            f"{result.get('simulation_status')!r}"
        )
    artifact_paths = [
        Path(path)
        for path in [*result.get("sio_files", ()), *result.get("dataset_files", ())]
    ]
    usable = [path for path in artifact_paths if path.is_file() and path.stat().st_size > 0]
    if not usable:
        errors.append("Momentum produced no non-empty SIO or ADS dataset")

    convergence = release_mesh_check(release_evidence)
    release_checks = {
        "mesh_convergence": convergence,
        "note": "This runner performs one solve; convergence is never inferred.",
    }
    if mode == "release" and convergence["status"] != "passed":
        errors.append(
            f"release check mesh_convergence is {convergence['status']}"
        )
    return errors, release_checks


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


def _failure_path(
    config: dict[str, Any], config_path: Path, *, output_preexisted: bool = False
) -> Path:
    raw = config.get("output_dir")
    if isinstance(raw, str) and raw.strip():
        output = Path(raw).expanduser()
        if not output.is_absolute():
            output = config_path.resolve().parent / output
        output = output.resolve()
        if not output_preexisted and output.is_dir():
            return output / "status.json"
        return output.parent / f"{output.name}_failure_status.json"
    return config_path.with_name(f"{config_path.stem}_failure_status.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Configure and run a generic ADS RFPro Momentum analysis."
    )
    parser.add_argument("config", type=Path, help="JSON Momentum configuration")
    parser.add_argument(
        "--configure-only",
        action="store_true",
        help="Validate config and write run_plan/status without importing ADS.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config_path = args.config.resolve()
    config: dict[str, Any] = {}
    status: dict[str, Any] = {
        "schema_version": 1,
        "stage": "momentum_em",
        "passed": False,
        "config": str(config_path),
    }
    output_preexisted = False
    try:
        if args.timeout_seconds <= 0:
            raise ValueError("timeout-seconds must be positive")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config = resolve_config_paths(config, config_path)
        output_preexisted = Path(config["output_dir"]).exists()
        validate_config(config)
        plan = build_run_plan(config)
        workspace_path = Path(config["workspace"])
        if not workspace_path.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace_path}")
        output_dir = Path(config["output_dir"])
        output_dir.mkdir(parents=True)
        plan_path = output_dir / "run_plan.json"
        status_path = output_dir / "status.json"
        _write_json(plan_path, plan)
        status.update(
            {
                "mode": plan["mode"],
                "workspace": str(workspace_path),
                "design": ":".join(plan["layout_lcv"]),
                "output_dir": str(output_dir),
                "run_plan": str(plan_path),
            }
        )
        if args.configure_only:
            status.update(
                {
                    "stage": "momentum_configuration",
                    "configured": True,
                    "configuration_passed": True,
                    "passed": True,
                    "passed_scope": "configuration_only",
                    "simulation_check": {
                        "status": "not_run",
                        "passed": False,
                    },
                    "flow_passed": False,
                    "release_passed": False,
                    "release_checks": {
                        "mesh_convergence": {
                            "status": "not_verified",
                            "verified": False,
                        },
                        "note": "configure-only does not claim a completed solve.",
                    },
                }
            )
        else:
            # Import the multi-interpreter bridge only after complete offline validation.
            import keysight.edatoolbox.multi_python as multi_python

            with multi_python.ads_context() as ads_context:
                status["rfpro_view"] = ads_context.call(
                    ads_create_or_verify_rfpro_view,
                    args=[
                        str(workspace_path),
                        plan["layout_lcv"],
                        plan["rfpro_view"],
                        plan["substrate"],
                    ],
                )
            with multi_python.xxpro_context() as xxpro_context:
                result = xxpro_context.call(
                    xxpro_run_momentum,
                    args=[
                        str(workspace_path),
                        plan,
                        str(output_dir),
                        float(args.timeout_seconds),
                    ],
                )
            errors, release_checks = validate_run_result(
                result,
                mode=plan["mode"],
                release_evidence=plan["release_evidence"],
            )
            status.update(
                {
                    "momentum": result,
                    "flow_passed": not any(
                        message.startswith("Momentum") for message in errors
                    ),
                    "release_checks": release_checks,
                    "release_passed": (
                        plan["mode"] == "release" and not errors
                    ),
                    "configuration_passed": True,
                    "simulation_check": {
                        "status": "passed" if not any(
                            message.startswith("Momentum") for message in errors
                        ) else "failed",
                        "passed": not any(
                            message.startswith("Momentum") for message in errors
                        ),
                    },
                    "passed_scope": plan["mode"],
                    "validation_errors": errors,
                    "passed": not errors,
                }
            )
        _write_json(status_path, status)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["passed"] else 2
    except Exception as exc:
        status.update(
            {
                "passed": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        try:
            _write_json(
                collision_safe_path(
                    _failure_path(
                        config,
                        config_path,
                        output_preexisted=output_preexisted,
                    )
                ),
                status,
            )
        except Exception:
            pass
        print(json.dumps(status, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
