"""Pure helpers for ADS DVE evidence, AEL paths, and application lifecycle checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


KNOWN_ADS_STARTUP_MODAL_TITLES = frozenset({"Get Started", "Swap Component"})
ADS_MAIN_WINDOW_PREFIX = "Advanced Design System"


def classify_ads_window_action(
    record: Mapping[str, Any],
    *,
    owned_process_ids: set[int],
    preexisting_handles: set[int],
) -> str | None:
    """Return a safe action for a new window owned by this ADS automation run."""
    handle = int(record.get("handle", -1))
    process_id = int(record.get("pid", -1))
    title = str(record.get("title", "")).strip()
    visible = bool(record.get("visible", False))

    if handle in preexisting_handles or process_id not in owned_process_ids or not visible:
        return None
    if title in KNOWN_ADS_STARTUP_MODAL_TITLES:
        return "closed"
    if title.startswith(ADS_MAIN_WINDOW_PREFIX):
        return "hidden"
    return None


def evaluate_ads_app_lifecycle(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a full-application AEL run without requiring non-empty GUI logs."""
    owned_process_ids = {int(value) for value in evidence.get("owned_process_ids", [])}
    preexisting_handles = {int(value) for value in evidence.get("preexisting_handles", [])}
    invalid_window_events: list[dict[str, Any]] = []
    for index, raw_event in enumerate(evidence.get("window_events", [])):
        event = dict(raw_event)
        expected = classify_ads_window_action(
            event,
            owned_process_ids=owned_process_ids,
            preexisting_handles=preexisting_handles,
        )
        if str(event.get("action", "")) != str(expected or ""):
            invalid_window_events.append(
                {
                    "index": index,
                    "recorded_action": event.get("action"),
                    "expected_action": expected,
                    "handle": event.get("handle"),
                    "pid": event.get("pid"),
                    "title": event.get("title"),
                }
            )

    try:
        stdout_bytes = int(evidence.get("stdout_bytes", -1))
        stderr_bytes = int(evidence.get("stderr_bytes", -1))
    except (TypeError, ValueError):
        stdout_bytes = stderr_bytes = -1

    checks = {
        "application_return_code_zero": int(evidence.get("application_return_code", -1))
        == 0,
        "application_did_not_time_out": not bool(evidence.get("timed_out", True)),
        "status_file_exists": bool(evidence.get("status_file_exists", False)),
        "status_file_nonempty": bool(evidence.get("status_file_nonempty", False)),
        "application_logs_accounted_for": stdout_bytes >= 0 and stderr_bytes >= 0,
        "owned_process_identity_recorded": bool(owned_process_ids),
        "window_actions_are_owned_and_allowlisted": not invalid_window_events,
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {
        "checks": checks,
        "errors": errors,
        "invalid_window_events": invalid_window_events,
        "passed": not errors,
    }


def evaluate_dve_job_evidence(
    evidence: Mapping[str, Any], *, require_zero_warnings: bool = True
) -> dict[str, Any]:
    """Reject a terminal-looking DVE job that loaded no rules or processed no geometry."""
    checks = {
        "application_return_code_zero": int(evidence.get("application_return_code", -1)) == 0,
        "run_status_success": str(evidence.get("run_status", "0")) == "1",
        "error_count_zero": int(evidence.get("error_count", -1)) == 0,
        "warning_count_acceptable": (
            int(evidence.get("warning_count", -1)) == 0
            if require_zero_warnings
            else int(evidence.get("warning_count", -1)) >= 0
        ),
        "job_status_complete": str(evidence.get("job_status", "")).casefold()
        == "complete",
        "report_status_complete": str(evidence.get("report_status", "")).casefold()
        == "complete",
        "rules_loaded": int(evidence.get("total_rules", 0)) > 0,
        "geometry_processed": int(evidence.get("shapes", 0)) > 0,
        "job_error_log_empty": not str(evidence.get("job_errors", "")).strip(),
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {"checks": checks, "errors": errors, "passed": not errors}


def _ael_path(path: Path | str) -> str:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_absolute():
        raise ValueError(f"AEL path is not absolute: {path}")
    return str(resolved).replace("\\", "/").replace('"', '\\"')


def instantiate_ael_driver(template: str, paths: Mapping[str, Path | str]) -> str:
    """Replace path tokens before ADS launch; do not rely on AEL getenv inheritance."""
    rendered = str(template)
    for name, path in paths.items():
        token = f"@@{str(name).upper()}@@"
        if token not in rendered:
            raise ValueError(f"AEL template is missing token {token}")
        rendered = rendered.replace(token, _ael_path(path))
    if "@@" in rendered:
        raise ValueError("AEL template still contains unresolved tokens")
    if "getenv" in rendered.casefold():
        raise ValueError("instantiated AEL driver must not depend on getenv()")
    return rendered


def dve_rule_location_root(rule_file: Path | str) -> Path:
    """Return the location passed to DVE when the deck lives in <root>/rules/."""
    rule = Path(rule_file).expanduser().resolve()
    if rule.parent.name.casefold() != "rules":
        raise ValueError("DVE rule file must be inside a directory named 'rules'")
    return rule.parent.parent
