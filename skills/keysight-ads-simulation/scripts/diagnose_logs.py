"""Classify ADS logs without requiring ADS Python or a license checkout."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from ads_common import ads_version_hint


PATTERNS = {
    "license_errors": [
        re.compile(r"license\s+(?:checkout\s+)?(?:failed|denied)", re.I),
        re.compile(r"FlexNet Licensing error", re.I),
        re.compile(r"Flex(?:Net|lm).*?(?:error\s*)?-(?:15|96)\b", re.I),
        re.compile(r"cannot connect to (?:the )?license server", re.I),
        re.compile(r"(?:unable|failed) to check ?out(?:\s+.+)?license", re.I),
        re.compile(r"license (?:server|manager).*(?:down|unavailable|not responding)", re.I),
        re.compile(r"No such feature exists", re.I),
        re.compile(r"Licensed number of users already reached", re.I),
        re.compile(r"feature\s+.+\s+(?:unavailable|not available)", re.I),
    ],
    "fatal_errors": [
        re.compile(r"fatal error", re.I),
        re.compile(r"^\s*ERROR\s*:", re.I),
        re.compile(
            r"Error detected by hpeesofsim during (?:netlist (?:parsing|flattening)|circuit set ?up)",
            re.I,
        ),
        re.compile(r"simulation aborted", re.I),
        re.compile(r"unrecoverable error", re.I),
        re.compile(r"segmentation fault|access violation", re.I),
        re.compile(r"floating[- ]point exception|numeric overflow", re.I),
    ],
    "convergence_errors": [
        re.compile(r"failed to converge|did not converge|convergence failure", re.I),
        re.compile(r"iteration limit (?:was )?reached", re.I),
        re.compile(r"singular Jacobian", re.I),
    ],
    "precision_warnings": [
        re.compile(r"HB truncation error may be present", re.I),
        re.compile(r"truncation error", re.I),
    ],
    "optional_library_warnings": [
        re.compile(r"SystemVue.*(?:not found|missing|unable)", re.I),
        re.compile(r"vtb\.defs", re.I),
    ],
}


def _hit(source: str, number: int, line: str) -> dict[str, Any]:
    return {"source": source, "line": number, "text": line.strip()}


def classify_text(text: str, source: str = "<memory>") -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "ok",
        "sources": [source],
        "license_errors": [],
        "fatal_errors": [],
        "convergence_errors": [],
        "precision_warnings": [],
        "optional_library_warnings": [],
        "other_warnings": [],
    }
    categorized_lines: set[int] = set()
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        for category, patterns in PATTERNS.items():
            if any(pattern.search(line) for pattern in patterns):
                result[category].append(_hit(source, number, line))
                categorized_lines.add(number)
    for number, line in enumerate(lines, start=1):
        if number not in categorized_lines and re.search(r"\bwarn(?:ing)?\b", line, re.I):
            result["other_warnings"].append(_hit(source, number, line))
    if not text.strip():
        result["fatal_errors"].append(_hit(source, 0, "Empty log file"))
    blocking = result["license_errors"] + result["fatal_errors"] + result["convergence_errors"]
    warning = result["precision_warnings"] + result["optional_library_warnings"] + result["other_warnings"]
    result["status"] = "failed" if blocking else ("warning" if warning else "ok")
    return result


def merge_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "tool": "diagnose_logs",
        "status": "ok",
        "sources": [],
        "license_errors": [],
        "fatal_errors": [],
        "convergence_errors": [],
        "precision_warnings": [],
        "optional_library_warnings": [],
        "other_warnings": [],
    }
    for result in results:
        for key in merged:
            if isinstance(merged[key], list):
                merged[key].extend(result.get(key, []))
    blocking = merged["license_errors"] + merged["fatal_errors"] + merged["convergence_errors"]
    warnings = merged["precision_warnings"] + merged["optional_library_warnings"] + merged["other_warnings"]
    merged["status"] = "failed" if blocking else ("warning" if warnings else "ok")
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results = []
    missing = []
    for path in args.logs:
        if not path.is_file():
            missing.append(str(path.resolve()))
            continue
        results.append(classify_text(path.read_text(encoding="utf-8", errors="replace"), str(path.resolve())))
    merged = merge_results(results)
    if missing:
        merged["fatal_errors"].extend(
            {"source": path, "line": 0, "text": "Log file not found"} for path in missing
        )
        merged["status"] = "failed"
    blocking = merged["license_errors"] + merged["fatal_errors"] + merged["convergence_errors"]
    warnings = (
        merged["precision_warnings"]
        + merged["optional_library_warnings"]
        + merged["other_warnings"]
    )
    merged.update(
        {
            "ads_version": ads_version_hint(),
            "de_api_version": None,
            "workspace": None,
            "netlist": None,
            "dataset": None,
            "return_code": 2 if merged["status"] == "failed" else 0,
            "warnings": warnings,
            "fatal_errors": blocking,
            "metrics": {
                "source_count": len(merged["sources"]),
                "license_error_count": len(merged["license_errors"]),
                "fatal_error_count": len(merged["fatal_errors"]),
                "convergence_error_count": len(merged["convergence_errors"]),
                "precision_warning_count": len(merged["precision_warnings"]),
                "optional_library_warning_count": len(merged["optional_library_warnings"]),
                "other_warning_count": len(merged["other_warnings"]),
            },
        }
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(merged, ensure_ascii=False, indent=2))
    return int(merged["return_code"])


if __name__ == "__main__":
    raise SystemExit(main())
