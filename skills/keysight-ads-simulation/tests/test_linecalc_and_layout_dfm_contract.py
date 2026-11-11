from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"
REFERENCE = SKILL_ROOT / "references" / "layout-em-and-fabrication.md"
OFFICIAL_INDEX = SKILL_ROOT / "references" / "official-doc-index.md"
LINECALC_SCRIPT = SKILL_ROOT / "scripts" / "run_linecalc.py"


def load_linecalc():
    if not LINECALC_SCRIPT.is_file():
        raise AssertionError(f"missing reusable LineCalc runner: {LINECALC_SCRIPT}")
    spec = importlib.util.spec_from_file_location("run_linecalc", LINECALC_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {LINECALC_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LineCalcContract(unittest.TestCase):
    def test_skill_routes_linecalc_and_installs_a_reusable_runner(self) -> None:
        frontmatter = SKILL.read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn("LineCalc", frontmatter)
        self.assertTrue(LINECALC_SCRIPT.is_file())

    def test_official_index_contains_linecalc_ael_and_cpwg_pages(self) -> None:
        text = OFFICIAL_INDEX.read_text(encoding="utf-8")
        for term in (
            "LineCalc_AEL_Functions.html",
            "lcuiuser_synthesize().html",
            "lcuiuser_file_save_as_ok().html",
            "CPWG_(Coplanar_Waveguide_with_Lower_Ground_Plane).html",
        ):
            self.assertIn(term, text)

    def test_cpwg_macro_and_native_lcs_parser_are_data_first(self) -> None:
        module = load_linecalc()
        macro = module.build_cpwg_macro(
            output_path=Path(r"C:\work\cpwg_result.lcs"),
            er=3.48,
            substrate_height_mm=0.8,
            copper_thickness_mm=0.018,
            loss_tangent=0.0037,
            conductivity_s_per_m=5.7e7,
            gap_mm=0.15,
            length_mm=8.0,
            frequency_ghz=2.4,
            target_impedance_ohm=50.0,
        )
        for term in (
            'lcuiuser_elemid_select("CPWG_DEFAULT")',
            "lcuiuser_synthesize()",
            'lcuiuser_file_save_as_ok("C:/work/cpwg_result.lcs")',
        ):
            self.assertIn(term, macro)
        self.assertNotIn("lcuiuser_file_exit", macro)
        self.assertNotIn('lcuiuser_set_physical_parms_fix("L"', macro)

        native = """
ELEMENT CPWG "CPWG_DEFAULT" 2 UNITS PHYSICAL PHYSICAL_FIXED SUBST ELECTRICAL RESULT
UNITS UNITS_DEFAULT FREQ_VAL=2.4 FREQ=GHz LENGTH=mm RES=Ohm ANGLE=deg
PHYSICAL W=1.234567 mm L=8.000000 mm
PHYSICAL_FIXED G=0.15 mm
ELECTRICAL Z0=50 Ohm E_Eff=45.000000 deg
RESULT K_Eff=2.90000 A_DB=0.050000
""".strip()
        parsed = module.parse_linecalc_lcs(native)
        self.assertAlmostEqual(1.234567, parsed["width_mm"])
        self.assertAlmostEqual(0.15, parsed["gap_mm"])
        self.assertAlmostEqual(50.0, parsed["impedance_ohm"])
        self.assertEqual(["G"], parsed["fixed_physical_parameters"])

    def test_zero_exit_launcher_does_not_preempt_delayed_linecalcui_result(self) -> None:
        module = load_linecalc()
        native = """
ELEMENT CPWG "CPWG_DEFAULT" 2 UNITS PHYSICAL PHYSICAL_FIXED SUBST ELECTRICAL RESULT
UNITS UNITS_DEFAULT FREQ_VAL=2.4 FREQ=GHz LENGTH=mm RES=Ohm ANGLE=deg
PHYSICAL W=1.234567 mm L=8.000000 mm
PHYSICAL_FIXED G=0.15 mm
ELECTRICAL Z0=50 Ohm E_Eff=45.000000 deg
RESULT K_Eff=2.90000 A_DB=0.050000
""".strip()

        class ExitedLauncher:
            pid = 12345
            returncode = 0

            def poll(self):
                return 0

            def terminate(self):
                raise AssertionError("an exited launcher must not be terminated")

            def wait(self, timeout=None):
                return 0

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "delayed.lcs"
            macro = root / "delayed.lcm"

            def create_result(_seconds):
                output.write_text(native, encoding="utf-8")

            with (
                patch.object(module.subprocess, "Popen", return_value=ExitedLauncher()),
                patch.object(module.time, "sleep", side_effect=create_result),
            ):
                result = module.run_linecalc(
                    linecalc_exe=root / "linecalc.exe",
                    macro_path=macro,
                    output_path=output,
                    macro_text="lcuiuser_synthesize();\n",
                    timeout_s=1.0,
                )
        self.assertAlmostEqual(1.234567, result["result"]["width_mm"])
        self.assertEqual(0, result["launcher_return_code"])


class LayoutDfmContract(unittest.TestCase):
    def test_reference_adds_geometry_gates_missing_from_different_net_drc(self) -> None:
        text = REFERENCE.read_text(encoding="utf-8")
        for term in (
            "DifferentNetScope",
            "same-net inter-component pad overlap",
            "soldermask web",
            "silkscreen-to-pad",
            "copper transition polygons",
            "wide connector land",
            "LineCalc",
        ):
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
