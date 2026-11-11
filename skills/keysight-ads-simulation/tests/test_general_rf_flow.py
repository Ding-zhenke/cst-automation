from __future__ import annotations

import importlib.util
import contextlib
import io
import math
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
REFERENCES = SKILL_ROOT / "references"


def load_script(name: str):
    path = SCRIPTS / name
    if not path.is_file():
        raise AssertionError(f"missing script: {path}")
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


class GeneralRfRoutingContract(unittest.TestCase):
    def test_skill_routes_five_circuit_families_and_two_validation_levels(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").casefold()
        for term in ("mixer", "amplifier", "oscillator", "filter", "rf switch"):
            self.assertIn(term, text)
        for term in ("flow", "release", "linear-rf-workflows.md", "nonlinear-rf-workflows.md"):
            self.assertIn(term, text)

    def test_linear_reference_defines_minimum_dc_sp_and_state_flows(self) -> None:
        path = REFERENCES / "linear-rf-workflows.md"
        self.assertTrue(path.is_file(), f"missing reference: {path}")
        text = path.read_text(encoding="utf-8")
        for term in (
            "Amplifier",
            "Filter",
            "RF switch",
            "S[2,1]",
            "state sweep",
            "20*log10",
            "Momentum",
        ):
            self.assertIn(term, text)

    def test_nonlinear_reference_defines_mixer_and_oscillator_flows(self) -> None:
        path = REFERENCES / "nonlinear-rf-workflows.md"
        self.assertTrue(path.is_file(), f"missing reference: {path}")
        text = path.read_text(encoding="utf-8")
        for term in (
            "Freq[1]",
            "Freq[2]",
            "IF is an output",
            "OscProbe",
            "OscPort",
            "phase noise",
        ):
            self.assertIn(term, text)

    def test_official_index_contains_all_rf_family_routes(self) -> None:
        text = (REFERENCES / "official-doc-index.md").read_text(encoding="utf-8")
        for term in (
            "Amplifier_QuickStart_Guide.html",
            "LearnOsc_wrk.7zads",
            "ex_lpf.py",
            "Designing_MMIC_SPDT_Switch.html",
            "Creating_a_Layout_from_a_Schematic.html",
        ):
            self.assertIn(term, text)


class DatasetModeContract(unittest.TestCase):
    def test_analysis_kinds_cover_general_rf_results(self) -> None:
        analyze = load_script("analyze_dataset.py")
        self.assertTrue(hasattr(analyze, "ANALYSIS_KINDS"))
        self.assertEqual(
            {"inventory", "voltage-spectrum", "sparameter", "oscillator", "state-sweep"},
            set(analyze.ANALYSIS_KINDS),
        )

    def test_sparameter_uses_dimensionless_twenty_log_magnitude(self) -> None:
        analyze = load_script("analyze_dataset.py")
        self.assertTrue(hasattr(analyze, "sparameter_to_db"))
        self.assertAlmostEqual(-6.020599913279624, analyze.sparameter_to_db(0.5 + 0j))
        self.assertEqual(float("-inf"), analyze.sparameter_to_db(0j))

    def test_ads_axis_lookup_is_case_insensitive_for_known_variants(self) -> None:
        analyze = load_script("analyze_dataset.py")

        class Frame:
            columns = ["mix[1]", "PORTZ[1]"]

        try:
            mix = analyze._find_column(Frame(), "Mix[1]")
            port_z = analyze._find_column(Frame(), "PortZ[1]")
        except KeyError as exc:
            self.fail(f"known ADS axis capitalization was not accepted: {exc}")
        self.assertEqual("mix[1]", mix)
        self.assertEqual("PORTZ[1]", port_z)

    def test_sparameter_frame_reports_db_without_power_fields(self) -> None:
        import pandas as pd

        analyze = load_script("analyze_dataset.py")
        self.assertTrue(hasattr(analyze, "analyze_frame"))
        frame = pd.DataFrame(
            {"freq": [1.0e9, 2.0e9], "S[2,1]": [0.5 + 0j, 0.25 + 0j]}
        )
        result = analyze.analyze_frame(
            frame, kind="sparameter", variable="S[2,1]"
        )
        self.assertEqual("dB", result["unit"])
        self.assertAlmostEqual(-6.020599913279624, result["values_db"][0])
        self.assertNotIn("power_dbm", result)

    def test_oscillator_and_state_sweep_smoke_use_presence_not_thresholds(self) -> None:
        import pandas as pd

        analyze = load_script("analyze_dataset.py")
        self.assertTrue(hasattr(analyze, "analyze_frame"))
        oscillator = pd.DataFrame(
            {"freq": [0.0, 1.0e9, 2.0e9], "Vout": [0j, 0.1 + 0j, 0.01 + 0j]}
        )
        osc_result = analyze.analyze_frame(
            oscillator, kind="oscillator", variable="Vout"
        )
        self.assertEqual(1.0e9, osc_result["oscillation_frequency_hz"])
        self.assertGreater(osc_result["fundamental_magnitude"], 0.0)

        states = pd.DataFrame(
            {
                "state": [0, 0, 1, 1],
                "freq": [1.0e9, 2.0e9, 1.0e9, 2.0e9],
                "S[2,1]": [0.8 + 0j, 0.7 + 0j, 0.02 + 0j, 0.03 + 0j],
            }
        )
        state_result = analyze.analyze_frame(
            states,
            kind="state-sweep",
            variable="S[2,1]",
            state_column="state",
            required_states=[0, 1],
        )
        self.assertEqual([0, 1], state_result["states"])
        self.assertEqual(4, state_result["row_count"])


class CapabilityPreflightContract(unittest.TestCase):
    def test_preflight_only_plans_requested_capability_imports(self) -> None:
        preflight = load_script("ads_preflight.py")
        self.assertTrue(hasattr(preflight, "parse_required_capabilities"))
        self.assertTrue(hasattr(preflight, "modules_for_capabilities"))
        required = preflight.parse_required_capabilities(["dataset"])
        self.assertEqual(("dataset",), required)
        modules = [module for _, module in preflight.modules_for_capabilities(required)]
        self.assertEqual(["keysight.ads.dataset"], modules)
        self.assertNotIn("keysight.ads.dds", modules)
        self.assertNotIn("keysight.ads.de", modules)

    def test_dds_is_imported_before_dataset_when_both_are_requested(self) -> None:
        preflight = load_script("ads_preflight.py")
        self.assertTrue(hasattr(preflight, "parse_required_capabilities"))
        self.assertTrue(hasattr(preflight, "modules_for_capabilities"))
        required = preflight.parse_required_capabilities(["dataset,dds"])
        modules = [module for _, module in preflight.modules_for_capabilities(required)]
        self.assertLess(modules.index("keysight.ads.dds"), modules.index("keysight.ads.dataset"))

    def test_ael_capability_imports_real_ael_module(self) -> None:
        preflight = load_script("ads_preflight.py")
        required = preflight.parse_required_capabilities(["ael"])
        modules = [module for _, module in preflight.modules_for_capabilities(required)]
        self.assertIn("keysight.ads.ael", modules)
        self.assertNotEqual(["keysight.ads.de"], modules)


class GeneralRunnerContract(unittest.TestCase):
    def test_runner_refuses_existing_output_and_ambiguous_input(self) -> None:
        runner = load_script("run_circuit_simulation.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            netlist = root / "input.net"
            netlist.write_text("Options ResourceUsage=no", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                runner.validate_run_inputs(
                    workspace=None,
                    design=None,
                    netlist=netlist,
                    output_dir=root,
                )
            with self.assertRaises(ValueError):
                runner.validate_run_inputs(
                    workspace=root,
                    design="lib:cell:schematic",
                    netlist=netlist,
                    output_dir=root / "new-output",
                )

    def test_mixer_optional_artifacts_are_disabled_by_default(self) -> None:
        mixer = load_script("mixer_smoke_test.py")
        args = mixer.build_parser().parse_args(["--workspace", "new_wrk"])
        self.assertTrue(hasattr(args, "with_dds"))
        self.assertTrue(hasattr(args, "with_reopen"))
        self.assertTrue(hasattr(args, "with_report"))
        self.assertFalse(args.with_dds)
        self.assertFalse(args.with_reopen)
        self.assertFalse(args.with_report)

    def test_runner_main_never_changes_status_inside_preexisting_output(self) -> None:
        runner = load_script("run_circuit_simulation.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            netlist = root / "input.net"
            netlist.write_text("Options ResourceUsage=no", encoding="utf-8")
            output = root / "existing-output"
            output.mkdir()
            sentinel = output / "status.json"
            original = '{"owner":"sentinel"}\n'
            sentinel.write_text(original, encoding="utf-8")
            argv = [
                "run_circuit_simulation.py",
                "--netlist",
                str(netlist),
                "--output-dir",
                str(output),
            ]
            old_argv = sys.argv
            try:
                sys.argv = argv
                with contextlib.redirect_stdout(io.StringIO()):
                    return_code = runner.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(2, return_code)
            self.assertEqual(original, sentinel.read_text(encoding="utf-8"))
            failures = list(root.glob("existing-output_failure_status*.json"))
            self.assertEqual(1, len(failures))


class PcbFlowContract(unittest.TestCase):
    def test_layout_and_momentum_modes_validate_without_ads_imports(self) -> None:
        layout = load_script("inspect_layout.py")
        momentum = load_script("run_momentum.py")
        self.assertEqual("flow", layout.validate_mode("flow"))
        self.assertEqual("release", layout.validate_mode("release"))
        config = {
            "workspace": "C:/example/design_wrk",
            "design": "Example_lib:Board:layout",
            "output_dir": "C:/example/em_run",
            "preset": "Momentum Microwave",
            "frequency": {"start_hz": 1.0e9, "stop_hz": 2.0e9, "points": 3},
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
        self.assertEqual(config, momentum.validate_config(config))

    def test_fabrication_paths_resolve_from_config_directory(self) -> None:
        exporter = load_script("export_layout_fabrication.py")
        self.assertTrue(hasattr(exporter, "resolve_config_paths"))
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "configs" / "export.json"
            config_path.parent.mkdir()
            config = {
                "workspace": "../board_wrk",
                "design": "Example_lib:Board:layout",
                "output_dir": "../out",
                "gerber_layermap": "maps/gerber.json",
                "drill_layermap": "maps/drill.json",
                "units": "mm",
                "integer_digits": 3,
                "fractional_digits": 3,
                "mode": "flow",
            }
            resolved = exporter.resolve_config_paths(config, config_path)
            self.assertEqual(
                (config_path.parent / "../board_wrk").resolve(),
                Path(resolved["workspace"]),
            )
            self.assertEqual("flow", resolved["mode"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
