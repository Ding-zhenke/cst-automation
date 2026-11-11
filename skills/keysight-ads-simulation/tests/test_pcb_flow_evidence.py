from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"


def load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    added = str(SCRIPTS) not in sys.path
    if added:
        sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(str(SCRIPTS))
    return module


class Named:
    def __init__(self, name: str):
        self.name = name


class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class Box:
    def __init__(self, x1: float, y1: float, x2: float, y2: float):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2


class LayoutEvidenceContract(unittest.TestCase):
    def test_existing_output_failure_status_never_overwrites_a_sentinel(self) -> None:
        layout = load_script("inspect_layout.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "layout_out"
            output.mkdir()
            sentinel = root / "layout_out_failure_status.json"
            sentinel.write_text("sentinel", encoding="utf-8")

            with redirect_stderr(io.StringIO()):
                result = layout.main(
                    [
                        "--workspace",
                        str(root / "missing_wrk"),
                        "--design",
                        "Demo_lib:Board:layout",
                        "--output",
                        str(output),
                    ]
                )

            self.assertEqual(1, result)
            self.assertEqual("sentinel", sentinel.read_text(encoding="utf-8"))
            numbered = root / "layout_out_failure_status_2.json"
            self.assertTrue(numbered.is_file())
            self.assertFalse(json.loads(numbered.read_text(encoding="utf-8"))["passed"])

    def test_geometry_bbox_is_preserved(self) -> None:
        layout = load_script("inspect_layout.py")

        class Shape:
            bbox = Box(0.1, 0.2, 3.4, 5.6)
            net = Named("RF")

        class Design:
            shapes = [Shape()]
            instances = []
            terms = []
            nets = [Named("RF")]

        inventory = layout.inventory_design(Design())
        self.assertEqual([0.1, 0.2, 3.4, 5.6], inventory["geometries"][0]["bbox"])

    def test_inventory_flattens_term_pins_and_never_reads_design_pins(self) -> None:
        layout = load_script("inspect_layout.py")

        class Pin:
            name = "RF_PIN"
            term_number = 7
            net = Named("RF")
            snap_point = Point(1.25, 2.5)
            has_any_pinfigs = True

            def get_pinfig_bbox(self):
                return Box(1.0, 2.0, 1.5, 3.0)

        class Term:
            name = "RF"
            number = 7
            net = Named("RF")
            pins = [Pin()]

        class Design:
            shapes = []
            instances = []
            terms = [Term()]
            nets = [Named("RF")]

            @property
            def pins(self):
                raise AssertionError("design.pins is not an ADS layout API")

        inventory = layout.inventory_design(Design())
        self.assertEqual(1, inventory["summary"]["pin_count"])
        pin = inventory["pins"][0]
        self.assertEqual(7, pin["term_number"])
        self.assertEqual("RF", pin["net"])
        self.assertEqual([1.25, 2.5], pin["snap_point"])
        self.assertTrue(pin["pinfig"]["has_any"])
        self.assertEqual([1.0, 2.0, 1.5, 3.0], pin["pinfig"]["bbox"])

    def test_em_stage_requires_ports_but_fabrication_stage_does_not(self) -> None:
        layout = load_script("inspect_layout.py")
        inventory = {"summary": {"non_empty": True, "port_count": 0}}
        self.assertTrue(
            any(
                "port" in message.casefold()
                for message in layout.validate_inventory(
                    inventory, require_ports=True
                )
            )
        )
        self.assertFalse(
            layout.validate_inventory(inventory, require_ports=False)
        )
        self.assertTrue(layout.resolve_require_ports("em", None))
        self.assertFalse(layout.resolve_require_ports("fabrication", None))

    def test_em_stage_requires_a_verified_substrate(self) -> None:
        layout = load_script("inspect_layout.py")
        inventory = {
            "summary": {"non_empty": True, "port_count": 1},
            "substrate": {"status": "not_applicable"},
        }
        errors = layout.validate_inventory(
            inventory,
            require_ports=True,
            require_substrate=True,
        )
        self.assertTrue(any("substrate" in item.casefold() for item in errors))
        self.assertFalse(
            layout.validate_inventory(
                inventory,
                require_ports=False,
                require_substrate=False,
            )
        )

    def test_existing_workspace_is_refused_and_close_design_is_preferred(self) -> None:
        layout = load_script("inspect_layout.py")

        class De:
            @staticmethod
            def workspace_is_open():
                return True

        with self.assertRaises(RuntimeError):
            layout.require_workspace_slot(De())

        calls: list[str] = []

        class Design:
            def close_design(self):
                calls.append("close_design")

            def close(self):
                calls.append("close")

        layout.release_design_handle(Design())
        self.assertEqual(["close_design"], calls)

    def test_naked_release_counts_are_assertions_not_verified_evidence(self) -> None:
        layout = load_script("inspect_layout.py")
        checks, errors = layout._release_checks(
            "release", {"drc_error_count": 0, "unrouted_count": 0}
        )
        self.assertTrue(errors)
        for check in checks.values():
            self.assertEqual("not_verified", check["status"])
            self.assertFalse(check["verified"])
            self.assertEqual("caller_asserted", check["source"])


class MomentumEvidenceContract(unittest.TestCase):
    def test_existing_output_failure_status_never_overwrites_a_sentinel(self) -> None:
        momentum = load_script("run_momentum.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo_wrk").mkdir()
            output = root / "em_out"
            output.mkdir()
            sentinel = root / "em_out_failure_status.json"
            sentinel.write_text("sentinel", encoding="utf-8")
            config = {
                "workspace": "demo_wrk",
                "design": "Demo_lib:Board:layout",
                "output_dir": "em_out",
                "preset": "Momentum Microwave",
                "frequency": {
                    "start_hz": 1.0e9,
                    "stop_hz": 2.0e9,
                    "points": 3,
                },
                "ports": [
                    {
                        "name": "P1",
                        "plus_pin": "RF",
                        "minus_pin": "GND",
                        "reference_impedance_ohm": 50.0,
                    }
                ],
                "mode": "flow",
            }
            config_path = root / "momentum.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with redirect_stderr(io.StringIO()):
                result = momentum.main([str(config_path), "--configure-only"])

            self.assertEqual(1, result)
            self.assertEqual("sentinel", sentinel.read_text(encoding="utf-8"))
            numbered = root / "em_out_failure_status_2.json"
            self.assertTrue(numbered.is_file())
            self.assertFalse(json.loads(numbered.read_text(encoding="utf-8"))["passed"])

    def test_rfpro_binding_and_created_port_mapping_are_verified_exactly(self) -> None:
        momentum = load_script("run_momentum.py")

        class Ref:
            layout = ("Demo_lib", "Board", "layout")
            substrate = ("Demo_lib", "tech.subst")

        binding = momentum.validate_rfpro_design_refs(
            {0: Ref()},
            expected_layout=("Demo_lib", "Board", "layout"),
            expected_substrate=("Demo_lib", "tech.subst"),
        )
        self.assertEqual(["Demo_lib", "Board", "layout"], binding["layout"])
        self.assertEqual(["Demo_lib", "tech.subst"], binding["substrate"])

        planned = [
            {
                "name": "P1",
                "plus_pin": "RF",
                "minus_pin": "GND",
                "reference_impedance_ohm": 50.0,
                "feed_type": "SMD",
            }
        ]
        actual = [
            {
                "name": "P1",
                "plus_pins": ["RF"],
                "minus_pins": ["GND"],
                "reference_impedance_ohm": 50.0,
                "feed_type": "SMD",
            }
        ]
        self.assertFalse(momentum.validate_port_assignments(planned, actual))
        bad = [dict(actual[0], plus_pins=["WRONG"])]
        self.assertTrue(momentum.validate_port_assignments(planned, bad))

    def test_smd_and_closed_loop_feed_types_are_semantically_equivalent(self) -> None:
        momentum = load_script("run_momentum.py")
        planned = [
            {
                "name": "P1",
                "plus_pin": "RF",
                "minus_pin": "GND",
                "reference_impedance_ohm": 50.0,
                "feed_type": "SMD",
            }
        ]
        actual = [
            {
                "name": "P1",
                "plus_pins": ["RF"],
                "minus_pins": ["GND"],
                "reference_impedance_ohm": 50.0,
                "feed_type": "ClosedLoop",
            }
        ]
        self.assertFalse(momentum.validate_port_assignments(planned, actual))
        self.assertEqual("closed_loop", momentum.canonical_feed_type("SMD"))
        self.assertEqual("closed_loop", momentum.canonical_feed_type("ClosedLoop"))
        auto = [dict(actual[0], feed_type="Auto")]
        self.assertTrue(momentum.validate_port_assignments(planned, auto))
        self.assertEqual("vendor-new-mode", momentum.canonical_feed_type("vendor-new-mode"))

    def test_solved_is_successful_and_ready_is_not_terminal(self) -> None:
        momentum = load_script("run_momentum.py")
        self.assertIn("Solved", momentum.SUCCESS_TERMINAL_STATUSES)
        self.assertTrue(momentum.is_successful_terminal_status("Solved"))
        self.assertFalse(momentum.is_terminal_status("Ready"))

    def test_naked_release_boolean_is_not_verified(self) -> None:
        momentum = load_script("run_momentum.py")
        check = momentum.release_mesh_check({"mesh_convergence": True})
        self.assertEqual("not_verified", check["status"])
        self.assertFalse(check["verified"])
        self.assertEqual("caller_asserted", check["source"])

    def test_configure_only_status_has_unambiguous_scope(self) -> None:
        momentum = load_script("run_momentum.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo_wrk").mkdir()
            config = {
                "workspace": "demo_wrk",
                "design": "Demo_lib:Board:layout",
                "output_dir": "em_out",
                "preset": "Momentum Microwave",
                "frequency": {
                    "start_hz": 1.0e9,
                    "stop_hz": 2.0e9,
                    "points": 3,
                },
                "ports": [
                    {
                        "name": "P1",
                        "plus_pin": "RF",
                        "minus_pin": "GND",
                        "reference_impedance_ohm": 50.0,
                    }
                ],
                "mode": "flow",
            }
            config_path = root / "momentum.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(
                0, momentum.main([str(config_path), "--configure-only"])
            )
            status = json.loads(
                (root / "em_out" / "status.json").read_text(encoding="utf-8")
            )
            self.assertTrue(status["configuration_passed"])
            self.assertEqual("configuration_only", status["passed_scope"])
            self.assertEqual("not_run", status["simulation_check"]["status"])
            self.assertFalse(status["flow_passed"])
            self.assertFalse(status["release_passed"])


class CamEvidenceContract(unittest.TestCase):
    def test_naked_release_booleans_are_not_verified(self) -> None:
        cam = load_script("export_layout_fabrication.py")
        checks = cam._release_checks(
            {"release_evidence": {"geometry_parsed": True}}
        )
        self.assertEqual("not_verified", checks["geometry_parsed"]["status"])
        self.assertFalse(checks["geometry_parsed"]["verified"])
        self.assertEqual("caller_asserted", checks["geometry_parsed"]["source"])

    def test_detailed_status_is_preserved_and_failure_paths_are_collision_safe(self) -> None:
        cam = load_script("export_layout_fabrication.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "cam_out"
            output.mkdir()
            detailed = output / "status.json"
            detailed.write_text('{"detail": true}', encoding="utf-8")
            config_path = root / "export.json"
            config = {"output_dir": str(output)}
            self.assertIsNone(
                cam.select_failure_status_path(
                    config,
                    config_path,
                    output_preexisted=False,
                    detailed_status_written=True,
                )
            )
            base = root / "cam_out_failure_status.json"
            base.write_text("first", encoding="utf-8")
            candidate = cam.collision_safe_path(base)
            self.assertNotEqual(base, candidate)
            self.assertFalse(candidate.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
