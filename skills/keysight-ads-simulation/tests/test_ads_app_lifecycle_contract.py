from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"
TROUBLESHOOTING = SKILL_ROOT / "references" / "troubleshooting.md"
VERIFIER = SKILL_ROOT / "scripts" / "verify_dve_drc.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_dve_drc", VERIFIER)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {VERIFIER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdsApplicationDiscoveryContract(unittest.TestCase):
    def test_skill_description_covers_observed_application_mode_failures(self) -> None:
        frontmatter = SKILL.read_text(encoding="utf-8").split("---", 2)[1]
        for term in ("fopen(NULL)", "Get Started", "exit hangs"):
            self.assertIn(term, frontmatter)

    def test_troubleshooting_records_observed_gui_lifecycle_boundaries(self) -> None:
        text = TROUBLESHOOTING.read_text(encoding="utf-8")
        for term in (
            "STARTUPINFO",
            "CREATE_NO_WINDOW",
            "Qt main window",
            "process ID",
            "pre-existing handles",
            "empty stdout/stderr",
            "status file",
            "File Browser",
            "de.workspace_is_open()",
        ):
            self.assertIn(term, text)


class AdsApplicationLifecycleContract(unittest.TestCase):
    def test_only_new_owned_known_ads_windows_receive_an_action(self) -> None:
        module = load_verifier()
        classify = module.classify_ads_window_action
        kwargs = {"owned_process_ids": {101, 102}, "preexisting_handles": {7}}

        self.assertEqual(
            "hidden",
            classify(
                {
                    "handle": 10,
                    "pid": 101,
                    "title": "Advanced Design System 2026 Update 1 (Main)",
                    "visible": True,
                },
                **kwargs,
            ),
        )
        for title in ("Get Started", "Swap Component"):
            self.assertEqual(
                "closed",
                classify(
                    {"handle": 11, "pid": 102, "title": title, "visible": True},
                    **kwargs,
                ),
            )

        self.assertIsNone(
            classify(
                {"handle": 7, "pid": 101, "title": "Get Started", "visible": True},
                **kwargs,
            )
        )
        self.assertIsNone(
            classify(
                {"handle": 12, "pid": 999, "title": "Get Started", "visible": True},
                **kwargs,
            )
        )
        self.assertIsNone(
            classify(
                {"handle": 13, "pid": 101, "title": "DRC Error", "visible": True},
                **kwargs,
            )
        )

    def test_empty_gui_stdout_is_allowed_only_with_clean_structured_evidence(self) -> None:
        module = load_verifier()
        valid = {
            "application_return_code": 0,
            "timed_out": False,
            "status_file_exists": True,
            "status_file_nonempty": True,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "owned_process_ids": [101],
            "preexisting_handles": [7],
            "window_events": [
                {
                    "handle": 10,
                    "pid": 101,
                    "title": "Advanced Design System 2026 Update 1 (Main)",
                    "visible": True,
                    "action": "hidden",
                },
                {
                    "handle": 11,
                    "pid": 101,
                    "title": "Get Started",
                    "visible": True,
                    "action": "closed",
                },
            ],
        }
        result = module.evaluate_ads_app_lifecycle(valid)
        self.assertTrue(result["passed"], result["errors"])

        timed_out = dict(valid, timed_out=True)
        self.assertFalse(module.evaluate_ads_app_lifecycle(timed_out)["passed"])

        foreign_close = dict(valid)
        foreign_close["window_events"] = [
            {
                "handle": 12,
                "pid": 999,
                "title": "Get Started",
                "visible": True,
                "action": "closed",
            }
        ]
        self.assertFalse(module.evaluate_ads_app_lifecycle(foreign_close)["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
