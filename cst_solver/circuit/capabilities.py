"""Conservative capability discovery; installed files do not prove licensing."""
from cst_automation.circuit_schema import BLOCK_TYPES
from .adapter import CircuitError


def circuit_capabilities(*, probe="static", app=None):
    if probe not in ("static", "live"):
        raise CircuitError("circuit_spec_invalid", "probe must be static or live")
    from cst_solver.environment import get_cst_paths
    from pathlib import Path
    paths = get_cst_paths()
    root = Path(paths.install_path) if paths.install_path else None
    report = {"interfaces": True, "sdk_discovered": bool(paths.python_lib and Path(paths.python_lib).is_dir()),
              "documentation_discovered": bool(root and (root / "Online Help/Python/source/cst.interface.html").is_file()),
              "license": "unknown", "block_types": list(BLOCK_TYPES),
              "verification": {"circuit_readback": "not_run", "network": "not_run", "transient_cosim": "not_run"},
              "execution_completion_probe": "not_validated", "probe": probe}
    if probe == "live":
        if app is None:
            raise CircuitError("circuit_unavailable", "live probe requires an explicit connected app")
        from .adapter import NativeAdapter
        report["project_readback"] = NativeAdapter(app).inspect()
        report["verification"]["circuit_readback"] = "observed_not_accepted"
    return report
