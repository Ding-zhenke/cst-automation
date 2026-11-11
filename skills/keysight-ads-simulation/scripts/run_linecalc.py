"""Data-first ADS LineCalc CPWG synthesis with process-owned cleanup.

The Windows ``linecalc.exe`` command is an asynchronous launcher in the
validated ADS 2026 Update 1 environment.  A zero launcher return code does not
mean that the child ``linecalcui.exe`` process has finished writing its native
``.lcs`` result, so completion is based on a stable, non-empty result file.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Iterable, Mapping


def _ael_number(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"AEL numeric value must be finite: {value!r}")
    return f"{number:.12g}"


def _ael_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace('"', '\\"')


def _positive(name: str, value: float, *, allow_zero: bool = False) -> float:
    number = float(value)
    lower_ok = number >= 0.0 if allow_zero else number > 0.0
    if not math.isfinite(number) or not lower_ok:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {relation}: {value!r}")
    return number


def build_cpwg_macro(
    *,
    output_path: Path,
    er: float,
    substrate_height_mm: float,
    copper_thickness_mm: float,
    loss_tangent: float,
    conductivity_s_per_m: float,
    gap_mm: float,
    length_mm: float,
    frequency_ghz: float,
    target_impedance_ohm: float,
) -> str:
    """Build an AEL macro that fixes CPWG gap and synthesizes width.

    ``length_mm`` initializes LineCalc's secondary electrical-length solution;
    it is not claimed as fixed unless the native result lists it under
    ``PHYSICAL_FIXED``.
    """
    values = {
        "er": _positive("er", er),
        "substrate_height_mm": _positive("substrate_height_mm", substrate_height_mm),
        "copper_thickness_mm": _positive("copper_thickness_mm", copper_thickness_mm),
        "loss_tangent": _positive("loss_tangent", loss_tangent, allow_zero=True),
        "conductivity_s_per_m": _positive("conductivity_s_per_m", conductivity_s_per_m),
        "gap_mm": _positive("gap_mm", gap_mm),
        "length_mm": _positive("length_mm", length_mm),
        "frequency_ghz": _positive("frequency_ghz", frequency_ghz),
        "target_impedance_ohm": _positive("target_impedance_ohm", target_impedance_ohm),
    }
    output = _ael_path(Path(output_path))
    lines = [
        "lcuiuser_file_new();",
        'lcuiuser_elemid_select("CPWG_DEFAULT");',
        'lcuiuser_set_freq_unit("GHz");',
        f'lcuiuser_set_freq_value("{_ael_number(values["frequency_ghz"])}");',
        'lcuiuser_set_length_unit("mm");',
        'lcuiuser_set_phys_length_unit("W", "mm");',
        'lcuiuser_set_phys_length_unit("G", "mm");',
        'lcuiuser_set_phys_length_unit("L", "mm");',
        'lcuiuser_set_subst_length_unit("H", "mm");',
        'lcuiuser_set_subst_length_unit("T", "mm");',
        f'lcuiuser_set_subst_parm_value("Er", "{_ael_number(values["er"])}");',
        f'lcuiuser_set_subst_parm_value("H", "{_ael_number(values["substrate_height_mm"])}");',
        f'lcuiuser_set_subst_parm_value("T", "{_ael_number(values["copper_thickness_mm"])}");',
        f'lcuiuser_set_subst_parm_value("Cond", "{_ael_number(values["conductivity_s_per_m"])}");',
        f'lcuiuser_set_subst_parm_value("TanD", "{_ael_number(values["loss_tangent"])}");',
        f'lcuiuser_set_physical_parms("G", "{_ael_number(values["gap_mm"])}");',
        f'lcuiuser_set_physical_parms("L", "{_ael_number(values["length_mm"])}");',
        'lcuiuser_set_physical_parms_fix("W", 0);',
        'lcuiuser_set_physical_parms_fix("G", 1);',
        'lcuiuser_set_elec_res_unit("Z0", "ohm");',
        f'lcuiuser_set_electrical_parms("Z0", "{_ael_number(values["target_impedance_ohm"])}");',
        "lcuiuser_synthesize();",
        f'lcuiuser_file_save_as_ok("{output}");',
    ]
    # Do not append lcuiuser_file_exit(): that API opens a confirmation modal.
    return "\n".join(lines) + "\n"


def _value(text: str, name: str) -> float:
    match = re.search(
        rf"(?:^|\s){re.escape(name)}=([-+0-9.eE]+)(?:\s|$)", text, re.MULTILINE
    )
    if match is None:
        raise ValueError(f"LineCalc result is missing {name}")
    value = float(match.group(1))
    if not math.isfinite(value):
        raise ValueError(f"LineCalc result {name} is non-finite")
    return value


def parse_linecalc_lcs(text: str) -> dict[str, Any]:
    """Parse the native LineCalc result instead of reading values from a GUI."""
    element_match = re.search(r'^ELEMENT\s+(\S+)\s+"([^"]+)"', text, re.MULTILINE)
    if element_match is None:
        raise ValueError("LineCalc result is missing the ELEMENT record")
    fixed_match = re.search(r"^PHYSICAL_FIXED\s+(.*)$", text, re.MULTILINE)
    fixed_physical_parameters = (
        re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=", fixed_match.group(1))
        if fixed_match is not None
        else []
    )
    return {
        "element": element_match.group(1),
        "element_id": element_match.group(2),
        "width_mm": _value(text, "W"),
        "gap_mm": _value(text, "G"),
        "length_mm": _value(text, "L"),
        "impedance_ohm": _value(text, "Z0"),
        "effective_er": _value(text, "K_Eff"),
        "frequency_ghz": _value(text, "FREQ_VAL"),
        "fixed_physical_parameters": fixed_physical_parameters,
    }


def _linecalcui_window_pids(output_path: Path) -> list[int]:
    """Return only LineCalc UI PIDs whose title contains this unique result."""
    if os.name != "nt":
        return []
    marker = str(Path(output_path).resolve()).replace("\\", "/").lower()
    user32 = ctypes.windll.user32
    matches: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def visit(window, _parameter):
        length = int(user32.GetWindowTextLengthW(window))
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(window, buffer, length + 1)
        title = buffer.value.replace("\\", "/").lower()
        if marker in title:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
            if pid.value:
                matches.append(int(pid.value))
        return True

    user32.EnumWindows(callback_type(visit), 0)
    return sorted(set(matches))


def _terminate_owned_linecalcui(output_path: Path) -> list[int]:
    """Stop only LineCalc UI children proven to own this run's output window."""
    terminated: list[int] = []
    try:
        import psutil
    except ImportError:
        return terminated
    for pid in _linecalcui_window_pids(output_path):
        try:
            child = psutil.Process(pid)
            if child.name().lower() != "linecalcui.exe":
                continue
            child.terminate()
            try:
                child.wait(timeout=5.0)
            except psutil.TimeoutExpired:
                child.kill()
                child.wait(timeout=5.0)
            terminated.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return terminated


def run_linecalc(
    *,
    linecalc_exe: Path,
    macro_path: Path,
    output_path: Path,
    macro_text: str,
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    """Run one LineCalc macro and wait for a stable native ``.lcs`` result."""
    linecalc_exe = Path(linecalc_exe).resolve()
    macro_path = Path(macro_path).resolve()
    output_path = Path(output_path).resolve()
    timeout_s = _positive("timeout_s", timeout_s)
    macro_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if macro_path.exists():
        raise FileExistsError(f"refusing to replace LineCalc macro: {macro_path}")
    if output_path.exists():
        raise FileExistsError(f"refusing to replace LineCalc result: {output_path}")
    macro_path.write_text(macro_text, encoding="utf-8")

    command = [str(linecalc_exe), "-m", str(macro_path)]
    environment = os.environ.copy()
    environment.setdefault("HPEESOF_DIR", str(linecalc_exe.parent.parent))
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    process = subprocess.Popen(
        command,
        cwd=str(macro_path.parent),
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    deadline = time.monotonic() + timeout_s
    previous_size = -1
    stable_observations = 0
    launcher_terminated = False
    try:
        while time.monotonic() < deadline:
            if output_path.is_file():
                size = output_path.stat().st_size
                if size > 0 and size == previous_size:
                    stable_observations += 1
                    if stable_observations >= 2:
                        break
                else:
                    previous_size = size
                    stable_observations = 0
            return_code = process.poll()
            # A zero code only says that the Windows launcher accepted the macro.
            if return_code not in (None, 0) and not output_path.is_file():
                raise RuntimeError(
                    f"ADS LineCalc launcher exited with code {return_code} without "
                    f"creating {output_path}"
                )
            time.sleep(0.05)
        else:
            raise TimeoutError(
                f"ADS LineCalc did not create a stable result within {timeout_s:g} s"
            )
        parsed = parse_linecalc_lcs(
            output_path.read_text(encoding="utf-8", errors="replace")
        )
    finally:
        if process.poll() is None:
            process.terminate()
            launcher_terminated = True
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)
        terminated_children = _terminate_owned_linecalcui(output_path)
    return {
        "command": command,
        "process_id": int(process.pid),
        "macro": str(macro_path),
        "native_result": str(output_path),
        "launcher_return_code": process.poll(),
        "owned_launcher_terminated": launcher_terminated,
        "owned_child_processes_terminated": terminated_children,
        "result": parsed,
    }


def _required_mapping(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"LineCalc config requires an object named {name!r}")
    return value


def synthesize_cpwg_from_config(
    *, config_path: Path, ads_root: Path, output_dir: Path
) -> dict[str, Any]:
    """Synthesize CPWG width from a reusable JSON configuration."""
    config_path = Path(config_path).resolve()
    ads_root = Path(ads_root).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to replace LineCalc output: {output_dir}")
    output_dir.mkdir(parents=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, Mapping):
        raise ValueError("LineCalc config root must be a JSON object")
    substrate = _required_mapping(config, "substrate")
    line = _required_mapping(config, "line")
    macro_path = output_dir / "cpwg_synthesis.lcm"
    output_path = output_dir / "cpwg_synthesis.lcs"
    macro = build_cpwg_macro(
        output_path=output_path,
        er=float(substrate["er"]),
        substrate_height_mm=float(substrate["height_mm"]),
        copper_thickness_mm=float(substrate["copper_thickness_mm"]),
        loss_tangent=float(substrate["loss_tangent"]),
        conductivity_s_per_m=float(substrate["conductivity_s_per_m"]),
        gap_mm=float(line["gap_mm"]),
        length_mm=float(line["length_mm"]),
        frequency_ghz=float(config["frequency_ghz"]),
        target_impedance_ohm=float(config["target_impedance_ohm"]),
    )
    linecalc_exe = ads_root / "bin" / "linecalc.exe"
    if not linecalc_exe.is_file():
        raise FileNotFoundError(f"ADS LineCalc executable not found: {linecalc_exe}")
    run = run_linecalc(
        linecalc_exe=linecalc_exe,
        macro_path=macro_path,
        output_path=output_path,
        macro_text=macro,
        timeout_s=float(config.get("timeout_s", 45.0)),
    )
    result = run["result"]
    width = float(result["width_mm"])
    gap = float(result["gap_mm"])
    height = float(substrate["height_mm"])
    impedance_tolerance = _positive(
        "impedance_tolerance_ohm",
        float(config.get("impedance_tolerance_ohm", 0.5)),
        allow_zero=True,
    )
    target = float(config["target_impedance_ohm"])
    checks = {
        "element_is_cpwg_default": result["element_id"] == "CPWG_DEFAULT",
        "impedance_within_tolerance": abs(float(result["impedance_ohm"]) - target)
        <= impedance_tolerance,
        "fixed_gap_matches_config": abs(gap - float(line["gap_mm"])) <= 1e-6,
        "gap_reported_fixed": "G" in result["fixed_physical_parameters"],
        "width_left_free_for_synthesis": "W" not in result["fixed_physical_parameters"],
        "cpwg_gap_model_range": 0.125 * width <= gap <= 4.5 * width,
        "cpwg_total_width_model_range": width + 2.0 * gap <= 10.0 * height,
    }
    payload = {
        "schema_version": 1,
        "tool": "run_linecalc",
        "config": str(config_path),
        "ads_root": str(ads_root),
        "requested_inputs": {
            "initial_length_mm": float(line["length_mm"]),
            "fixed_gap_mm": float(line["gap_mm"]),
            "target_impedance_ohm": target,
        },
        "run": run,
        "checks": checks,
        "passed": all(checks.values()),
    }
    (output_dir / "linecalc_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "status.json").write_text(
        json.dumps(
            {
                "tool": "run_linecalc",
                "status": "passed" if payload["passed"] else "failed",
                "return_code": 0 if payload["passed"] else 2,
                "metrics": result,
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return payload


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synthesize a CPWG width with ADS LineCalc and parse the native result"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--ads-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    output_existed = args.output_dir.exists()
    try:
        payload = synthesize_cpwg_from_config(
            config_path=args.config,
            ads_root=args.ads_root,
            output_dir=args.output_dir,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["passed"] else 2
    except Exception as exc:
        payload = {
            "tool": "run_linecalc",
            "status": "failed",
            "return_code": 1,
            "fatal_errors": [str(exc)],
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
        if not output_existed:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            (args.output_dir / "status.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
