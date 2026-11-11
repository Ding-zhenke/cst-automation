from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"
REFERENCE = SKILL_ROOT / "references" / "layout-em-and-fabrication.md"
SCRIPTS = SKILL_ROOT / "scripts"


def load_script(name: str):
    path = SCRIPTS / name
    if not path.is_file():
        raise AssertionError(f"missing reusable script: {path}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DveReleaseContract(unittest.TestCase):
    def test_skill_routes_dve_drc_and_cam_roundtrip(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("DVE DRC", text)
        self.assertIn("CAM round-trip", text)

    def test_reference_records_full_app_dve_and_nonempty_work_contract(self) -> None:
        text = REFERENCE.read_text(encoding="utf-8")
        for required in (
            "ads.exe -m",
            "dve_create_drc_job",
            "totalRules",
            "shapes",
            "getenv",
            "fopen",
            "NULL",
            "one directory above",
        ):
            self.assertIn(required, text)

    def test_dve_zero_rule_or_zero_shape_run_cannot_pass(self) -> None:
        module = load_script("verify_dve_drc.py")
        valid = {
            "application_return_code": 0,
            "run_status": 1,
            "error_count": 0,
            "warning_count": 0,
            "job_status": "Complete",
            "report_status": "Complete",
            "total_rules": 1,
            "shapes": 92,
            "job_errors": "",
        }
        self.assertTrue(module.evaluate_dve_job_evidence(valid)["passed"])
        for key in ("total_rules", "shapes"):
            invalid = dict(valid, **{key: 0})
            self.assertFalse(module.evaluate_dve_job_evidence(invalid)["passed"], key)

    def test_ael_driver_requires_instantiated_absolute_paths(self) -> None:
        module = load_script("verify_dve_drc.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = {
                "workspace": root / "board_wrk",
                "rule_file": root / "drc" / "rules" / "width.ael",
                "status_file": root / "drc" / "status.txt",
            }
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
            driver = module.instantiate_ael_driver(
                'decl ws="@@WORKSPACE@@"; decl rules="@@RULE_FILE@@"; decl out="@@STATUS_FILE@@";',
                paths,
            )
            self.assertNotIn("@@", driver)
            self.assertNotIn("getenv", driver)
            for path in paths.values():
                self.assertIn(str(path.resolve()).replace("\\", "/"), driver)


class CamRoundtripContract(unittest.TestCase):
    def test_reference_records_importer_zero_shape_and_layer_number_boundaries(self) -> None:
        text = REFERENCE.read_text(encoding="utf-8")
        for required in (
            "gbr_create_importer",
            "gbr_import_design",
            "zero drill shapes",
            "independent Excellon parser",
            "dedicated verification layer",
            "LayerId.create_layer_id_from_library",
            ".layer",
            "nested workspace",
        ):
            self.assertIn(required, text)

    def test_excellon_parser_and_independent_materialization_can_close_drill_gate(self) -> None:
        module = load_script("verify_cam_roundtrip.py")
        payload = (
            "; Format : 3.3, Leading Zeros Suppressed\n"
            "M48\nMETRIC,LZ,000.000\nT01C0.300000\n%\nM71\nG90\nT01\n"
            "X0011Y0162\nY0219\nM30\n"
        )
        parsed = module.parse_ads_excellon(payload)
        self.assertEqual([(1.1, 16.2), (1.1, 21.9)], parsed["points_mm"])
        evidence = {
            "official_ads_drill_shapes": 0,
            "source_pth_count": 2,
            "parsed_drill_count": 2,
            "materialized_verification_shapes": 2,
            "coordinates_match_source": True,
            "tool_diameters_mm": [0.3],
            "required_gerber_layers_nonempty": True,
            "outline_matches": True,
            "top_copper_relative_error": 0.0,
            "bottom_copper_relative_error": 0.0,
            "copper_area_tolerance": 0.01,
            "limitation_disclosed": True,
        }
        result = module.evaluate_cam_roundtrip_evidence(evidence)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual("independent_excellon_materialization", result["drill_gate_method"])
        evidence["materialized_verification_shapes"] = 0
        self.assertFalse(module.evaluate_cam_roundtrip_evidence(evidence)["passed"])

    def test_drill_gate_uses_source_database_count_not_a_fixed_constant(self) -> None:
        module = load_script("verify_cam_roundtrip.py")
        evidence = {
            "official_ads_drill_shapes": 0,
            "source_pth_count": 46,
            "parsed_drill_count": 42,
            "materialized_verification_shapes": 42,
            "coordinates_match_source": True,
            "tool_diameters_mm": [0.3],
            "required_gerber_layers_nonempty": True,
            "outline_matches": True,
            "top_copper_relative_error": 0.0,
            "bottom_copper_relative_error": 0.0,
            "copper_area_tolerance": 0.01,
            "limitation_disclosed": True,
        }
        result = module.evaluate_cam_roundtrip_evidence(evidence)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["pth_count_matches_source"])

    def test_official_drill_import_does_not_require_independent_materialization(self) -> None:
        module = load_script("verify_cam_roundtrip.py")
        evidence = {
            "official_ads_drill_shapes": 3,
            "source_pth_count": 3,
            "parsed_drill_count": 3,
            "coordinates_match_source": True,
            "required_gerber_layers_nonempty": True,
            "outline_matches": True,
            "top_copper_relative_error": 0.0,
            "bottom_copper_relative_error": 0.0,
            "copper_area_tolerance": 0.01,
        }
        result = module.evaluate_cam_roundtrip_evidence(evidence)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual("official_ads_import", result["drill_gate_method"])

    def test_verification_workspace_must_not_be_nested(self) -> None:
        module = load_script("verify_cam_roundtrip.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source_wrk"
            source.mkdir()
            with self.assertRaises(ValueError):
                module.require_non_nested_verification_workspace(
                    source, source / "verification_wrk"
                )
            sibling = root / "verification_wrk"
            self.assertEqual(
                sibling.resolve(),
                module.require_non_nested_verification_workspace(source, sibling),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
