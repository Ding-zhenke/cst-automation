"""Saved schematic result access; never falls back to 3D or run zero."""
import csv
import hashlib
import json
import math
from pathlib import Path

from cst_solver.environment import _load_cst_module
from .adapter import CircuitError


def quantity_values(values):
    units = set()
    numbers = []
    array_unit = getattr(values, "unit", None)
    for item in values:
        unit = getattr(item, "unit", array_unit)
        if unit is None:
            raise CircuitError("circuit_result_read_failed", "Result unit is unknown; no inferred unit substituted")
        units.add(str(unit))
        value = complex(getattr(item, "value", item))
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise CircuitError("circuit_result_read_failed", "Non-finite result sample")
        numbers.append(value)
    if len(units) != 1 or not numbers:
        raise CircuitError("circuit_result_read_failed", "Empty curve or inconsistent units")
    return numbers, units.pop()


class CircuitResult:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        if not Path(self.path).is_file():
            raise CircuitError("circuit_result_read_failed", "Saved project not found", path=self.path)
        try:
            self.project = _load_cst_module("cst.results").ProjectFile(self.path, allow_interactive=True)
            self.module = self.project.get_schematic()
        except Exception as exc:
            raise CircuitError("circuit_result_read_failed", str(exc), path=self.path) from exc

    def get_tree_items(self, *, task_name=None):
        try:
            items = [str(item) for item in self.module.get_tree_items()]
            return [p for p in items if task_name is None or p.startswith(task_name + "\\")]
        except Exception as exc:
            raise CircuitError("circuit_result_read_failed", str(exc)) from exc

    def get_run_ids(self, tree_path):
        if tree_path not in self.get_tree_items():
            raise CircuitError("circuit_result_read_failed", "Result tree item not found", tree_path=tree_path)
        return list(self.module.get_run_ids(tree_path))

    def get_parameter_combination(self, run_id):
        if type(run_id) is not int:
            raise CircuitError("circuit_result_read_failed", "run_id must be an integer")
        try:
            return dict(self.module.get_parameter_combination(run_id))
        except Exception as exc:
            raise CircuitError("circuit_result_read_failed", str(exc), run_id=run_id) from exc

    def read_curve(self, tree_path, *, run_id):
        if type(run_id) is not int or run_id not in self.get_run_ids(tree_path):
            raise CircuitError("circuit_result_read_failed", "Requested run is unavailable", tree_path=tree_path, run_id=run_id)
        try:
            item = self.module.get_result_item(tree_path, run_id=run_id)
            x, xu = quantity_values(item.get_xdata())
            y, yu = quantity_values(item.get_ydata())
            if len(x) != len(y) or any(v.imag != 0 for v in x):
                raise CircuitError("circuit_result_read_failed", "Axis mismatch or complex x axis")
            samples = [[a.real, b.real, b.imag] for a, b in zip(x, y)]
            digest = hashlib.sha256(json.dumps(samples, allow_nan=False).encode()).hexdigest()
            return {"x": [v.real for v in x], "y": y, "x_unit": xu, "y_unit": yu,
                    "domain": "schematic", "project_path": self.path, "tree_path": tree_path, "run_id": run_id,
                    "parameters": self.get_parameter_combination(run_id), "sample_digest": digest,
                    "amplitude_convention": "unknown", "current_direction": "unknown", "fft_window": "unknown"}
        except CircuitError:
            raise
        except Exception as exc:
            raise CircuitError("circuit_result_read_failed", str(exc), tree_path=tree_path, run_id=run_id) from exc

    def export_csv(self, tree_path, destination, *, run_id):
        path = Path(destination).resolve()
        meta_path = Path(str(path) + ".json")
        if path.suffix.lower() != ".csv" or path.exists() or meta_path.exists() or path == Path(self.path):
            raise CircuitError("circuit_result_read_failed", "Export requires a new .csv and new metadata path; no overwrite", destination=str(path))
        curve = self.read_curve(tree_path, run_id=run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([f'x [{curve["x_unit"]}]', f'y_real [{curve["y_unit"]}]', f'y_imag [{curve["y_unit"]}]'])
            writer.writerows((x, y.real, y.imag) for x, y in zip(curve["x"], curve["y"]))
        metadata = {k: v for k, v in curve.items() if k not in ("x", "y")}
        with meta_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata, ensure_ascii=False, indent=2))
        return {"metadata": metadata, "artifacts": [str(path.resolve()), str(meta_path.resolve())]}
