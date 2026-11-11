from pathlib import Path
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_TEXT = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
DATA_TEXT = (SKILL_DIR / "references" / "dataset-and-dds.md").read_text(
    encoding="utf-8"
)
DESIGN_TEXT = (SKILL_DIR / "references" / "design-and-simulation.md").read_text(
    encoding="utf-8"
)
TROUBLE_TEXT = (SKILL_DIR / "references" / "troubleshooting.md").read_text(
    encoding="utf-8"
)


class DataFirstSkillContract(unittest.TestCase):
    def test_skill_declares_dataset_as_numeric_source_of_truth(self):
        self.assertIn("source of truth for numerical acceptance", SKILL_TEXT)

    def test_skill_does_not_require_gui_for_headless_acceptance(self):
        self.assertNotIn("only for the final visual check", SKILL_TEXT)
        self.assertNotIn("the final visible-window check passed", SKILL_TEXT)
        self.assertIn("GUI check is not applicable", SKILL_TEXT)

    def test_skill_forbids_reading_numbers_from_screenshots(self):
        self.assertIn("Never derive numerical values from screenshots", SKILL_TEXT)

    def test_dataset_reference_records_mixer_and_dds_pitfalls(self):
        for required in (
            "Mix[1]",
            "|V|^2 / (2R)",
            "Attempting to access a deleted object",
            "transparent backgrounds",
        ):
            self.assertIn(required, DATA_TEXT)

    def test_design_reference_records_ads_2026_u1_api_pitfalls(self):
        for required in (
            'de.db.Transaction(design, "description")',
            "inst_term_numbered(n).inst_pins[0].snap_point",
            "check that the parameter exists",
        ):
            self.assertIn(required, DESIGN_TEXT)

    def test_troubleshooting_separates_model_limits_from_solver_success(self):
        for required in (
            "no DC path to ground (topology corrected)",
            "ideal symmetry upper bound",
            "Do not claim S11 optimization",
        ):
            self.assertIn(required, TROUBLE_TEXT)


if __name__ == "__main__":
    unittest.main()
