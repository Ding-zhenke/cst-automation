"""Shared, dependency-free helpers for the ADS skill command-line tools."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


def base_status(tool: str) -> dict[str, Any]:
    """Return the stable JSON envelope used by every skill tool."""
    return {
        "tool": tool,
        "status": "pending",
        "ads_version": ads_version_hint(),
        "de_api_version": None,
        "workspace": None,
        "netlist": None,
        "dataset": None,
        "return_code": None,
        "warnings": [],
        "fatal_errors": [],
        "metrics": {},
    }


def require_new_path(path: str | Path) -> Path:
    """Reject an existing target; ADS workspace creation is never destructive."""
    target = Path(path).expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing target: {target}")
    return target


def failure_status_path(workspace: str | Path, *, existed_before: bool) -> Path:
    """Choose a failure-report path without writing into a pre-existing workspace."""
    target = Path(workspace).expanduser().resolve()
    if not existed_before and target.is_dir():
        return target / "verification_result.json"
    return target.parent / f"{target.name}_failure.json"


def voltage_to_dbm(voltage: complex | float, reference_ohms: float = 50.0) -> float:
    """Convert an ADS peak-voltage phasor to available power in dBm."""
    if reference_ohms <= 0:
        raise ValueError("reference_ohms must be positive")
    power_w = abs(voltage) ** 2 / (2.0 * reference_ohms)
    if power_w <= 0:
        return float("-inf")
    return 10.0 * math.log10(power_w / 1.0e-3)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag, "magnitude": abs(value)}
    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return str(value)
    return value


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2))


def ads_version_hint() -> str | None:
    root = os.environ.get("HPEESOF_DIR")
    return Path(root).name if root else None


def simulator_result_evidence(
    result: Any, *, none_means_check_call_success: bool = False
) -> dict[str, Any]:
    """Record the simulator result, including U1's check_call success convention."""
    evidence: dict[str, Any] = {
        "result_type": type(result).__name__,
        "return_code": None,
        "return_code_source": "not_exposed",
    }
    if result is None and none_means_check_call_success:
        evidence["return_code"] = 0
        evidence["return_code_source"] = "subprocess.check_call_success_no_exception"
        return evidence
    if isinstance(result, int):
        evidence["return_code"] = int(result)
        evidence["return_code_source"] = "integer_result"
        return evidence
    for attribute in ("returncode", "return_code"):
        value = getattr(result, attribute, None)
        if value is not None:
            evidence["return_code"] = int(value)
            evidence["return_code_source"] = attribute
            break
    return evidence
