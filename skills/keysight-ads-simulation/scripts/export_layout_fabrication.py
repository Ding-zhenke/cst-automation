from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_KEYS = (
    "workspace",
    "design",
    "output_dir",
    "gerber_layermap",
    "drill_layermap",
    "units",
    "integer_digits",
    "fractional_digits",
)

VALIDATION_MODES = ("flow", "release")
PATH_KEYS = (
    "workspace",
    "output_dir",
    "gerber_layermap",
    "drill_layermap",
)
RELEASE_CHECK_NAMES = (
    "geometry_parsed",
    "repeat_export_hash_match",
    "cam_roundtrip",
)


def validate_mode(mode: str | None) -> str:
    cooked = "flow" if mode is None else str(mode).strip().lower()
    if cooked not in VALIDATION_MODES:
        raise ValueError(f"mode must be one of {VALIDATION_MODES}, got {mode!r}")
    return cooked


def resolve_config_paths(
    config: dict[str, Any], config_path: Path | str
) -> dict[str, Any]:
    """Resolve path fields relative to the JSON file, never the caller's cwd."""
    base = Path(config_path).resolve().parent
    resolved = dict(config)
    for key in PATH_KEYS:
        raw = resolved.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = base / path
        resolved[key] = str(path.resolve())
    resolved["mode"] = validate_mode(resolved.get("mode", "flow"))
    return resolved


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_KEYS if key not in config]
    if missing:
        raise ValueError(f"missing fabrication config keys: {missing}")
    for key in ("workspace", "design", "output_dir", "gerber_layermap", "drill_layermap"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    if config["units"] != "mm":
        raise ValueError("only the verified 'mm' export path is supported")
    for key in ("integer_digits", "fractional_digits"):
        if not isinstance(config[key], int) or not 1 <= config[key] <= 6:
            raise ValueError(f"{key} must be an integer from 1 through 6")
    validate_mode(config.get("mode", "flow"))
    evidence = config.get("release_evidence", {})
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("release_evidence must be an object when provided")
    return config


def require_new_output(path: Path) -> Path:
    output = Path(path).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to replace fabrication output: {output}")
    return output


def release_design_handle(design: Any) -> None:
    """Prefer the documented db_uu close_design(), retaining old fallback support."""
    close = getattr(design, "close_design", None)
    if callable(close):
        close()
        return
    close = getattr(design, "close", None)
    if callable(close):
        close()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() not in {".log", ".json"}:
            size = path.stat().st_size
            records.append(
                {
                    "path": str(path.resolve()),
                    "relative_path": path.relative_to(directory).as_posix(),
                    "bytes": size,
                    "sha256": sha256_file(path) if size else None,
                }
            )
    return records


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _release_checks(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize externally produced release evidence without claiming to run it."""
    evidence = config.get("release_evidence") or {}
    result: dict[str, dict[str, Any]] = {}
    for name in RELEASE_CHECK_NAMES:
        raw = evidence.get(name)
        result[name] = {
            "status": "not_verified",
            "verified": False,
            "source": "caller_asserted" if raw is not None else None,
            "caller_value": raw,
        }
    return result


def export_layout_fabrication(config: dict[str, Any]) -> dict[str, Any]:
    config = validate_config(config)
    mode = validate_mode(config.get("mode", "flow"))
    workspace_path = Path(config["workspace"]).resolve()
    gerber_map = Path(config["gerber_layermap"]).resolve()
    drill_map = Path(config["drill_layermap"]).resolve()
    output_dir = require_new_output(Path(config["output_dir"]))
    if not workspace_path.is_dir():
        raise FileNotFoundError(f"workspace does not exist: {workspace_path}")
    for path in (gerber_map, drill_map):
        if not path.is_file():
            raise FileNotFoundError(f"layer map does not exist: {path}")

    gerber_dir = output_dir / "gerber_raw"
    drill_dir = output_dir / "drill_raw"
    gerber_dir.mkdir(parents=True)
    drill_dir.mkdir()

    # Import ADS only after pure validation so contract tests can run in normal Python.
    from keysight.ads import ael, de
    from keysight.ads.de import db_uu

    de.open_workspace(workspace_path)
    design = None
    try:
        design = db_uu.open_design(
            config["design"],
            de.db.DesignMode.READ_ONLY,
        )
        gerber = ael.call.gbr_create_exporter()
        ael.call.gbr_export_set_length_unit(gerber, ael.decl.GBR_LENGTH_UNIT_MM)
        ael.call.gbr_export_set_num_integer_digits(gerber, config["integer_digits"])
        ael.call.gbr_export_set_num_fractional_digits(
            gerber, config["fractional_digits"]
        )
        ael.call.gbr_export_set_file_format(gerber, ael.decl.GBR_FILE_FORMAT_RS274X)
        ael.call.gbr_export_set_scale_factor(gerber, 1.0)
        ael.call.gbr_export_set_layermap_path(gerber, str(gerber_map))
        ael.call.gbr_export_set_transfer_unmapped_layers(gerber, False)
        ael.call.gbr_export_set_log_path(gerber, str(output_dir / "gerber_export.log"))
        ael.call.gbr_export_design(gerber, design, str(gerber_dir))

        drill = ael.call.drl_create_exporter()
        ael.call.drl_export_set_length_unit(drill, ael.decl.DRL_LENGTH_UNIT_MM)
        ael.call.drl_export_set_num_integer_digits(drill, config["integer_digits"])
        ael.call.drl_export_set_num_fractional_digits(
            drill, config["fractional_digits"]
        )
        ael.call.drl_export_set_scale_factor(drill, 1.0)
        ael.call.drl_export_set_layermap_path(drill, str(drill_map))
        ael.call.drl_export_set_transfer_unmapped_layers(drill, False)
        ael.call.drl_export_set_log_path(drill, str(output_dir / "drill_export.log"))
        ael.call.drl_export_design(drill, design, str(drill_dir))
    finally:
        if design is not None:
            release_design_handle(design)
        de.close_workspace()

    gerbers = _inventory(gerber_dir)
    drills = _inventory(drill_dir)
    validation_errors: list[str] = []
    if not gerbers:
        validation_errors.append("Gerber export produced no data files")
    if not drills:
        validation_errors.append("Drill export produced no data files")
    for record in [*gerbers, *drills]:
        if record["bytes"] <= 0:
            validation_errors.append(f"empty fabrication file: {record['relative_path']}")

    flow_passed = not validation_errors
    release_checks = _release_checks(config)
    if mode == "release":
        for name, check in release_checks.items():
            if check["status"] != "passed":
                validation_errors.append(
                    f"release check {name} is {check['status']}"
                )

    status = {
        "schema_version": 1,
        "stage": "ads_layout_fabrication_export",
        "passed": not validation_errors,
        "mode": mode,
        "flow_passed": flow_passed,
        "workspace": str(workspace_path),
        "design": config["design"],
        "output_dir": str(output_dir),
        "interfaces": [
            "gbr_create_exporter/gbr_export_design",
            "drl_create_exporter/drl_export_design",
        ],
        "gerber_files": gerbers,
        "drill_files": drills,
        "flow_checks": {
            "official_gerber_export": "passed" if gerbers else "failed",
            "official_drill_export": "passed" if drills else "failed",
            "all_exported_files_non_empty": (
                "passed"
                if gerbers
                and drills
                and all(record["bytes"] > 0 for record in [*gerbers, *drills])
                else "failed"
            ),
        },
        "release_checks": {
            "requested": mode == "release",
            "checks": release_checks,
            "note": (
                "Extra release evidence is caller-supplied and was not executed by "
                "this exporter."
            ),
        },
        "validation_errors": validation_errors,
    }
    _write_json(output_dir / "status.json", status)
    return status


def _failure_path(
    config: dict[str, Any], config_path: Path, *, output_preexisted: bool = False
) -> Path:
    raw_output = config.get("output_dir")
    if isinstance(raw_output, str) and raw_output.strip():
        output = Path(raw_output).expanduser()
        if not output.is_absolute():
            output = config_path.resolve().parent / output
        output = output.resolve()
        if not output_preexisted and output.is_dir():
            return output / "status.json"
        return output.parent / f"{output.name}_failure_status.json"
    return config_path.with_name(f"{config_path.stem}_failure_status.json")


def collision_safe_path(path: Path | str) -> Path:
    candidate = Path(path)
    if not candidate.exists():
        return candidate
    for index in range(2, 10000):
        numbered = candidate.with_name(
            f"{candidate.stem}_{index}{candidate.suffix}"
        )
        if not numbered.exists():
            return numbered
    raise RuntimeError(f"cannot allocate collision-safe failure path near {candidate}")


def select_failure_status_path(
    config: dict[str, Any],
    config_path: Path,
    *,
    output_preexisted: bool,
    detailed_status_written: bool,
) -> Path | None:
    if detailed_status_written:
        return None
    return collision_safe_path(
        _failure_path(
            config,
            config_path,
            output_preexisted=output_preexisted,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Gerber and Drill data from an openable ADS layout design."
    )
    parser.add_argument("config", type=Path, help="JSON export configuration")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config.resolve()
    config: dict[str, Any] = {}
    output_preexisted = False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config = resolve_config_paths(config, config_path)
        output_preexisted = Path(config["output_dir"]).exists()
        status = export_layout_fabrication(config)
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0 if status["passed"] else 2
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "stage": "ads_layout_fabrication_export",
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        try:
            raw_output = config.get("output_dir")
            detailed_status = (
                Path(raw_output) / "status.json"
                if isinstance(raw_output, str) and raw_output.strip()
                else None
            )
            failure_path = select_failure_status_path(
                config,
                config_path,
                output_preexisted=output_preexisted,
                detailed_status_written=bool(
                    detailed_status is not None and detailed_status.is_file()
                ),
            )
            if failure_path is not None:
                _write_json(failure_path, failure)
        except Exception:
            pass
        print(json.dumps(failure, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
