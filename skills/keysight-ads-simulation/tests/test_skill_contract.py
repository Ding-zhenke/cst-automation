from __future__ import annotations

import importlib.util
import json
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
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
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


class SkillStructureTests(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        expected = [
            "scripts/ads_common.py",
            "scripts/ads_preflight.py",
            "scripts/invoke_ads_python.ps1",
            "scripts/mixer_smoke_test.py",
            "scripts/analyze_dataset.py",
            "scripts/create_dds.py",
            "scripts/diagnose_logs.py",
            "scripts/verify_reopen.py",
            "scripts/run_circuit_simulation.py",
            "scripts/inspect_layout.py",
            "scripts/run_momentum.py",
            "scripts/run_linecalc.py",
            "references/official-doc-index.md",
            "references/environment-and-compatibility.md",
            "references/design-and-simulation.md",
            "references/dataset-and-dds.md",
            "references/linear-rf-workflows.md",
            "references/nonlinear-rf-workflows.md",
            "references/troubleshooting.md",
        ]
        missing = [item for item in expected if not (SKILL_ROOT / item).is_file()]
        self.assertEqual([], missing, f"Missing skill resources: {missing}")

    def test_skill_has_routes_and_no_template_markers(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("TODO", text)
        for required in (
            "official Python API",
            "flow",
            "release",
            "never overwrite",
            "GUI check is not applicable",
            "linear-rf-workflows.md",
            "nonlinear-rf-workflows.md",
        ):
            self.assertIn(required, text)
        self.assertNotIn("ADS_Mixer_SmokeTest_wrk", text)

    def test_openai_yaml_contract(self) -> None:
        text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Keysight ADS Simulation"', text)
        self.assertIn(
            'short_description: "Automate RF circuits, layouts, EM, and fabrication in ADS"',
            text,
        )
        self.assertIn("$keysight-ads-simulation", text)

    def test_project_agents_routes_ads_tasks_to_skill(self) -> None:
        agents_path = SKILL_ROOT.parents[2] / "AGENTS.md"
        if not agents_path.is_file():
            self.skipTest("project-level AGENTS.md is not part of the standalone skill package")
        agents = agents_path.read_text(encoding="utf-8")
        self.assertIn("$keysight-ads-simulation", agents)
        self.assertIn("ADS_Mixer_SmokeTest_wrk", agents)


class PureToolTests(unittest.TestCase):
    def test_voltage_to_dbm_uses_peak_phasor_convention(self) -> None:
        common = load_script("ads_common.py")
        peak_voltage_for_0_dbm = math.sqrt(2.0 * 50.0 * 1.0e-3)
        self.assertAlmostEqual(0.0, common.voltage_to_dbm(peak_voltage_for_0_dbm, 50.0), places=10)

    def test_existing_workspace_is_refused(self) -> None:
        common = load_script("ads_common.py")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                common.require_new_path(Path(directory))

    def test_failure_status_stays_outside_preexisting_workspace(self) -> None:
        common = load_script("ads_common.py")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "existing_wrk"
            workspace.mkdir()
            failure = common.failure_status_path(workspace, existed_before=True)
            self.assertEqual(workspace.parent, failure.parent)
            self.assertNotEqual(workspace / "verification_result.json", failure)

    def test_log_classifier_distinguishes_blocking_and_precision_warnings(self) -> None:
        diagnose = load_script("diagnose_logs.py")
        precision = diagnose.classify_text("HB truncation error may be present", "hb.log")
        self.assertTrue(precision["precision_warnings"])
        self.assertFalse(precision["fatal_errors"])
        self.assertFalse(precision["license_errors"])

        optional = diagnose.classify_text(
            "WARNING: Unable to find optional SystemVue vtb.defs INCLUDE", "de.log"
        )
        self.assertTrue(optional["optional_library_warnings"])
        self.assertFalse(optional["fatal_errors"])

        license_failure = diagnose.classify_text(
            "FlexNet Licensing error: License checkout failed", "sim.log"
        )
        self.assertTrue(license_failure["license_errors"])
        self.assertEqual("failed", license_failure["status"])

    def test_log_classifier_catches_real_ads_and_flexnet_failures(self) -> None:
        diagnose = load_script("diagnose_logs.py")
        for text in (
            "Error detected by hpeesofsim during netlist parsing.",
            "Error detected by hpeesofsim during netlist flattening.",
            "Error detected by hpeesofsim during circuit set up.",
            "ERROR: unknown component in generated netlist",
        ):
            result = diagnose.classify_text(text, "sim.log")
            self.assertEqual("failed", result["status"], text)
            self.assertTrue(result["fatal_errors"], text)

        for text in (
            "Cannot connect to license server system.",
            "FlexNet Licensing error:-15,570",
            "FLEXlm error -96: license server machine is down",
            "Unable to check out ADS harmonic balance license",
        ):
            result = diagnose.classify_text(text, "license.log")
            self.assertEqual("failed", result["status"], text)
            self.assertTrue(result["license_errors"], text)

    def test_empty_log_is_blocking(self) -> None:
        diagnose = load_script("diagnose_logs.py")
        result = diagnose.classify_text("\n", "empty.log")
        self.assertEqual("failed", result["status"])
        self.assertTrue(result["fatal_errors"])

    def test_dataset_block_selection_requires_identity_when_ambiguous(self) -> None:
        analyze = load_script("analyze_dataset.py")
        self.assertEqual("HB1.HB", analyze._select_block(["HB1.HB"], None))
        with self.assertRaises(ValueError):
            analyze._select_block(["DC1.DC", "SP1.SP"], None)
        with self.assertRaises(KeyError):
            analyze._select_block(["HB1.HB"], "SP1.SP")

    def test_dataset_metric_rejects_nonfinite_values(self) -> None:
        analyze = load_script("analyze_dataset.py")
        for value in (complex(float("nan"), 0), complex(float("inf"), 0)):
            with self.assertRaises(ValueError):
                analyze._validate_complex_metric(value, require_nonzero=False)
        with self.assertRaises(ValueError):
            analyze._validate_complex_metric(0j, require_nonzero=True)
        self.assertEqual(1 + 2j, analyze._validate_complex_metric(1 + 2j, require_nonzero=True))

    def test_headless_dds_marks_unrequested_gui_not_applicable(self) -> None:
        create_dds = load_script("create_dds.py")
        evidence = create_dds._headless_window_evidence(1)
        self.assertEqual(1, evidence["window_descriptor_count"])
        self.assertFalse(evidence["visible_window_verified"])
        self.assertEqual("not_applicable", evidence["visible_window_verification"])
        self.assertNotIn("visible_window_count", evidence)

    def test_headless_dds_cannot_satisfy_explicit_gui_gate(self) -> None:
        create_dds = load_script("create_dds.py")
        evidence = create_dds._headless_window_evidence(1, gui_required=True)
        self.assertFalse(evidence["visible_window_verified"])
        self.assertEqual("not_verified", evidence["visible_window_verification"])

    def test_difference_mix_index_follows_frequency_order(self) -> None:
        mixer = load_script("mixer_smoke_test.py")
        self.assertEqual([-1, 1], mixer._difference_mix_index(1.0e9, 1.1e9))
        self.assertEqual([1, -1], mixer._difference_mix_index(1.1e9, 1.0e9))

    def test_simulator_result_records_actual_return_code(self) -> None:
        common = load_script("ads_common.py")

        class Completed:
            returncode = 0

        evidence = common.simulator_result_evidence(Completed())
        self.assertEqual(0, evidence["return_code"])
        self.assertEqual("returncode", evidence["return_code_source"])
        missing = common.simulator_result_evidence(None)
        self.assertIsNone(missing["return_code"])
        self.assertEqual("not_exposed", missing["return_code_source"])
        u1_success = common.simulator_result_evidence(
            None, none_means_check_call_success=True
        )
        self.assertEqual(0, u1_success["return_code"])
        self.assertEqual(
            "subprocess.check_call_success_no_exception", u1_success["return_code_source"]
        )

    def test_reopen_log_collection_includes_solver_data_log(self) -> None:
        reopen = load_script("verify_reopen.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run.ckt.out").write_text("Simulation finished", encoding="utf-8")
            data_dir = root / "run_data"
            data_dir.mkdir()
            (data_dir / "logFile.txt").write_text(
                "An HB truncation error may be present.", encoding="utf-8"
            )
            diagnostics, paths = reopen._classify_saved_logs(root, [])
        self.assertEqual(2, len(paths))
        self.assertTrue(diagnostics["precision_warnings"])

    def test_mixer_source_keeps_two_grounded_sources_and_two_fundamentals(self) -> None:
        source = (SCRIPTS / "mixer_smoke_test.py").read_text(encoding="utf-8")
        self.assertIn('(-4, 0, "G_LO")', source)
        self.assertIn('(-4, -2, "G_RF")', source)
        self.assertIn('[f"{args.lo_frequency_hz:g} Hz", f"{args.rf_frequency_hz:g} Hz"]', source)
        self.assertNotIn('Freq[3]', source)

    def test_status_json_contains_required_fields(self) -> None:
        common = load_script("ads_common.py")
        status = common.base_status("unit-test")
        for key in (
            "tool",
            "status",
            "ads_version",
            "de_api_version",
            "workspace",
            "netlist",
            "dataset",
            "return_code",
            "warnings",
            "fatal_errors",
            "metrics",
        ):
            self.assertIn(key, status)
        json.dumps(status)


if __name__ == "__main__":
    unittest.main(verbosity=2)
