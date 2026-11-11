from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_TEXT = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
OFFICIAL_INDEX = (SKILL_ROOT / "references" / "official-doc-index.md").read_text(
    encoding="utf-8"
)
LAYOUT_REFERENCE = SKILL_ROOT / "references" / "layout-em-and-fabrication.md"
EXPORT_SCRIPT = SKILL_ROOT / "scripts" / "export_layout_fabrication.py"


def read_if_present(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def load_export_script():
    if not EXPORT_SCRIPT.is_file():
        raise AssertionError(f"missing reusable exporter: {EXPORT_SCRIPT}")
    spec = importlib.util.spec_from_file_location(EXPORT_SCRIPT.stem, EXPORT_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {EXPORT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LayoutEmFabricationContract(unittest.TestCase):
    def test_skill_routes_layout_em_and_fabrication_tasks(self) -> None:
        self.assertTrue(LAYOUT_REFERENCE.is_file())
        self.assertTrue(EXPORT_SCRIPT.is_file())
        self.assertIn("layout-em-and-fabrication.md", SKILL_TEXT)
        for trigger in ("layout", "Momentum", "Gerber", "Drill"):
            self.assertIn(trigger, SKILL_TEXT)

    def test_reference_records_verified_ads_2026_u1_layout_boundaries(self) -> None:
        text = read_if_present(LAYOUT_REFERENCE)
        for required in (
            "add_dot_for_pin",
            "add_via_with_specified_layers",
            "solder_mask_bottom:drawing",
            "LppDb",
            "generic THROUGH PCBPad",
            "No-Copper padstack",
            "Design does not expose close()",
        ):
            self.assertIn(required, text)

    def test_reference_records_momentum_evidence_chain(self) -> None:
        text = read_if_present(LAYOUT_REFERENCE)
        for required in (
            "simulation.status",
            "Completed",
            "proj.sio",
            "_sio2adsds_discrete",
            "keysight.pwdatatools",
            "Touchstone port order",
            "Calibration will not be used for port",
        ):
            self.assertIn(required, text)

    def test_reference_records_official_cam_export_contract(self) -> None:
        text = read_if_present(LAYOUT_REFERENCE)
        for required in (
            "gbr_create_exporter",
            "gbr_export_design",
            "drl_create_exporter",
            "drl_export_design",
            "open workspace",
            "non-empty",
            "SHA256",
            "not verified",
        ):
            self.assertIn(required, text)

    def test_official_index_routes_layout_em_and_cam_docs(self) -> None:
        for required in (
            "ex_create_layout.html",
            "ex_padstack.html",
            "ex_substrate_with_layout.html",
            "add_via_with_specified_layers",
            "LppDb",
            "xxpro",
            "Gerber_Functions.html",
            "Drill_Functions.html",
        ):
            self.assertIn(required, OFFICIAL_INDEX)

    def test_exporter_validates_config_without_importing_ads(self) -> None:
        module = load_export_script()
        valid = {
            "workspace": "C:/example/design_wrk",
            "design": "Example_lib:Board:layout",
            "output_dir": "C:/example/export_1",
            "gerber_layermap": "C:/example/gerber.json",
            "drill_layermap": "C:/example/drill.json",
            "units": "mm",
            "integer_digits": 3,
            "fractional_digits": 3,
        }
        self.assertEqual(valid, module.validate_config(valid))
        unverified_units = dict(valid, units="inch")
        with self.assertRaises(ValueError):
            module.validate_config(unverified_units)
        for key in tuple(valid):
            invalid = dict(valid)
            invalid.pop(key)
            with self.assertRaises(ValueError, msg=key):
                module.validate_config(invalid)

    def test_exporter_refuses_output_replacement_and_handles_design_release(self) -> None:
        module = load_export_script()
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory)
            with self.assertRaises(FileExistsError):
                module.require_new_output(existing)

        class WithoutClose:
            pass

        module.release_design_handle(WithoutClose())

        class WithClose:
            closed = False

            def close(self) -> None:
                self.closed = True

        handle = WithClose()
        module.release_design_handle(handle)
        self.assertTrue(handle.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
