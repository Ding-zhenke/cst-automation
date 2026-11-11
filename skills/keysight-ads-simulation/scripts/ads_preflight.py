"""Probe only the ADS APIs required by the current automation task."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import os
import platform
import sys
from pathlib import Path
from typing import Iterable

from ads_common import ads_version_hint, base_status, print_json, write_json


DEFAULT_CAPABILITIES = ("de", "dataset", "simulator")

# Keep DDS before Dataset. ADS 2026 U1 can fail when both APIs are imported in
# the opposite order in one Python process.
CAPABILITY_MODULES = {
    "dds": (("data_display", "keysight.ads.dds"),),
    "dataset": (("dataset", "keysight.ads.dataset"),),
    "de": (("design_environment", "keysight.ads.de"),),
    "simulator": (("circuit_simulator", "keysight.edatoolbox.ads"),),
    # Gerber/Drill export calls the dedicated AEL module after DE opens a design.
    "ael": (("ael", "keysight.ads.ael"),),
    # Momentum automation uses both the layout EM helpers and xxpro controller.
    "em": (
        ("em_tools", "keysight.ads.emtools"),
        ("momentum_controller", "keysight.edatoolbox.xxpro"),
    ),
}
_IMPORT_ORDER = ("dds", "dataset", "de", "simulator", "ael", "em")


def parse_required_capabilities(values: Iterable[str] | None) -> tuple[str, ...]:
    """Parse repeated/comma-separated ``--require`` values without importing ADS."""
    requested: list[str] = []
    source = list(values or ())
    if not source:
        source = [",".join(DEFAULT_CAPABILITIES)]
    for item in source:
        for raw in str(item).split(","):
            capability = raw.strip().casefold()
            if not capability:
                continue
            if capability not in CAPABILITY_MODULES:
                choices = ", ".join(sorted(CAPABILITY_MODULES))
                raise ValueError(f"Unknown ADS capability '{raw.strip()}'; choose from: {choices}")
            if capability not in requested:
                requested.append(capability)
    if not requested:
        raise ValueError("At least one ADS capability is required")
    return tuple(requested)


def modules_for_capabilities(required: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """Return the unique module import plan for the requested capabilities."""
    capabilities = parse_required_capabilities(required)
    planned: list[tuple[str, str]] = []
    seen_modules: set[str] = set()
    for capability in _IMPORT_ORDER:
        if capability not in capabilities:
            continue
        for friendly_name, module_name in CAPABILITY_MODULES[capability]:
            if module_name in seen_modules:
                continue
            planned.append((friendly_name, module_name))
            seen_modules.add(module_name)
    return tuple(planned)


def _required_executables(root: Path, required: tuple[str, ...]) -> dict[str, Path]:
    executables = {"bundled_python": root / "tools" / "python" / "python.exe"}
    if "de" in required or "ael" in required or "em" in required:
        executables["ads.exe"] = root / "bin" / "ads.exe"
    if "simulator" in required:
        executables["hpeesofsim.exe"] = root / "bin" / "hpeesofsim.exe"
    return executables


def run_preflight(required: Iterable[str] | None = None) -> dict:
    required_capabilities = parse_required_capabilities(required)
    status = base_status("ads_preflight")
    root_text = os.environ.get("HPEESOF_DIR")
    root = Path(root_text).resolve() if root_text else None
    status["ads_version"] = ads_version_hint()
    status["metrics"] = {
        "required_capabilities": list(required_capabilities),
        "module_import_plan": [
            {"name": name, "module": module}
            for name, module in modules_for_capabilities(required_capabilities)
        ],
        "ads_root": str(root) if root else None,
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "python_is_bundled": bool(root and Path(sys.executable).resolve().is_relative_to(root)),
        "executables": {},
        "apis": {},
        "documentation": {},
        "license_probe": "not_requested" if "de" not in required_capabilities else "not_run",
    }
    if root is None:
        status["fatal_errors"].append("HPEESOF_DIR is not set; use invoke_ads_python.ps1")
        status["status"] = "failed"
        status["return_code"] = 2
        return status

    for name, path in _required_executables(root, required_capabilities).items():
        status["metrics"]["executables"][name] = {"path": str(path), "exists": path.is_file()}
        if not path.is_file():
            status["fatal_errors"].append(f"Missing required executable: {path}")

    docs = {
        "de": root / "doc" / "python" / "de" / "html" / "index.html",
        "dataset": root / "doc" / "python" / "dataset" / "html" / "index.html",
        "dds": root / "doc" / "python" / "dds" / "html" / "index.html",
        "simulator": root
        / "doc"
        / "python"
        / "edatoolbox"
        / "html"
        / "API_Reference"
        / "ads"
        / "classes"
        / "circuit_simulator.html",
    }
    for capability in required_capabilities:
        path = docs.get(capability)
        if path is not None:
            status["metrics"]["documentation"][capability] = {
                "path": str(path),
                "exists": path.is_file(),
            }

    imported = {}
    for name, module_name in modules_for_capabilities(required_capabilities):
        try:
            imported[name] = importlib.import_module(module_name)
            status["metrics"]["apis"][name] = {"module": module_name, "available": True}
        except Exception as exc:  # ADS exposes some import/license failures as runtime errors.
            status["metrics"]["apis"][name] = {
                "module": module_name,
                "available": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            status["fatal_errors"].append(f"Cannot import {module_name}: {exc}")

    de = imported.get("design_environment")
    if de is not None and "de" in required_capabilities:
        try:
            status["de_api_version"] = int(de.version())
            status["metrics"]["de_product_version"] = str(de.product_version())
            status["metrics"]["license_probe"] = "DE API import and version query succeeded"
        except Exception as exc:
            status["fatal_errors"].append(f"DE API/license probe failed: {exc}")
            status["metrics"]["license_probe"] = "failed"

    if "simulator" in required_capabilities:
        try:
            status["metrics"]["keysight_edatoolbox_version"] = importlib.metadata.version(
                "keysight-edatoolbox"
            )
        except importlib.metadata.PackageNotFoundError:
            status["warnings"].append("keysight-edatoolbox package version metadata not found")

    if status["de_api_version"] not in (None, 635):
        status["warnings"].append(
            f"Untested DE API {status['de_api_version']}; validated baseline is API 635"
        )
    status["return_code"] = 0 if not status["fatal_errors"] else 2
    status["status"] = "ok" if not status["fatal_errors"] else "failed"
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require",
        action="append",
        help=(
            "Required capability or comma-separated capabilities. May be repeated; "
            "choices: de,dataset,dds,simulator,ael,em. Default: de,dataset,simulator"
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        required = parse_required_capabilities(args.require)
        status = run_preflight(required)
    except Exception as exc:
        status = base_status("ads_preflight")
        status["status"] = "failed"
        status["return_code"] = 2
        status["fatal_errors"].append(f"{type(exc).__name__}: {exc}")
    if args.output:
        write_json(args.output, status)
    print_json(status)
    return int(status["return_code"])


if __name__ == "__main__":
    raise SystemExit(main())
