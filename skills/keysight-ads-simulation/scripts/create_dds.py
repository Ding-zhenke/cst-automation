"""Create and structurally verify a native ADS Data Display without requiring its GUI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ads_common import base_status, print_json, write_json


def _headless_window_evidence(
    descriptor_count: int, *, gui_required: bool = False
) -> dict[str, Any]:
    """Describe saved DDS window state without claiming an interactive GUI exists."""
    verification = "not_verified" if gui_required else "not_applicable"
    note = (
        "Headless automation cannot verify a visible Data Display window"
        if gui_required
        else "GUI rendering was not requested; saved window descriptors are structural evidence only"
    )
    return {
        "window_descriptor_count": int(descriptor_count),
        "visible_window_verified": False,
        "visible_window_verification": verification,
        "visible_window_note": note,
    }


def _guard_output(path: Path | None, replace: bool) -> None:
    if path is not None and path.exists() and not replace:
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")


def _dds_base_path(dataset: Path, destination: Path) -> Path:
    """Return an ADS workspace-like root whose required data directory exists."""
    candidates = [dataset.parent, *dataset.parents, destination.parent, *destination.parents]
    for candidate in candidates:
        if (candidate / "data").is_dir():
            return candidate
    base = destination.parent
    (base / "data").mkdir(parents=True, exist_ok=True)
    return base


def create_data_display(
    dataset_path: str | Path,
    output_path: str | Path,
    *,
    trace_expression: str,
    title: str,
    marker_name: str | None = None,
    marker_value: str | float | None = None,
    equation: str | None = None,
    note: str | None = None,
    png_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    replace: bool = False,
    gui_required: bool = False,
) -> dict[str, Any]:
    import keysight.ads.dds as dds

    source = Path(dataset_path).resolve()
    destination = Path(output_path).resolve()
    png = Path(png_path).resolve() if png_path else None
    pdf = Path(pdf_path).resolve() if pdf_path else None
    if not source.is_file():
        raise FileNotFoundError(f"Dataset not found: {source}")
    for path in (destination, png, pdf):
        _guard_output(path, replace)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
    # ADS resolves a saved DDS file's default dataset directory as <dds-dir>/data.
    (destination.parent / "data").mkdir(parents=True, exist_ok=True)

    dds_base = _dds_base_path(source, destination)
    dds_file = dds.new_dds_file(dataset=str(source), path=dds_base)
    window_descriptor_count = 0
    try:
        page = dds_file.pages[0]
        plot = page.add_plot(traces=[trace_expression], title=title)
        trace = plot.traces[0]
        if marker_name and marker_value is not None:
            trace.add_marker(marker_name, marker_value)
        if equation:
            page.add_equation(equation)
        if note:
            page.add_text(note, (100, 100))

        if len(dds_file.windows) == 0:
            dds_file.new_window()
        dds_file.windows[0].current_page = page.name
        dds_file.windows[0].zoom_all()
        window_descriptor_count = len(dds_file.windows)
        dds_file.save(name=destination.name, path=destination.parent)
        if png:
            dds_file.print_all_pages(png)
        if pdf:
            dds_file.print_all_pages(pdf)
    finally:
        dds.close_dds_file(dds_file)

    required = [destination] + [path for path in (png, pdf) if path is not None]
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"DDS export did not create non-empty files: {missing}")
    return {
        "dataset": str(source),
        "dds": str(destination),
        "dds_base_path": str(dds_base),
        "trace_expression": trace_expression,
        "marker": {"name": marker_name, "value": marker_value} if marker_name else None,
        "equation": equation,
        **_headless_window_evidence(
            window_descriptor_count, gui_required=gui_required
        ),
        "png": str(png) if png else None,
        "pdf": str(pdf) if pdf else None,
    }


def inspect_data_display(
    dds_path: str | Path,
    *,
    expected_dataset: str | Path | None = None,
    expected_marker: str | None = None,
    gui_required: bool = False,
) -> dict[str, Any]:
    """Reload saved DDS content and verify its descriptors and dataset binding headlessly."""
    import keysight.ads.dds as dds

    source = Path(dds_path).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise FileNotFoundError(f"Non-empty DDS file not found: {source}")
    dds_file = dds.open_dds_file(source)
    try:
        raw_default_dataset = str(dds_file.default_dataset)
        default_dataset_path = Path(raw_default_dataset)
        if not default_dataset_path.is_absolute():
            default_dataset_path = (source.parent / default_dataset_path).resolve()
        else:
            default_dataset_path = default_dataset_path.resolve()

        page_names = [page.name for page in dds_file.pages]
        trace_expressions: list[str] = []
        markers: list[dict[str, Any]] = []
        for page in dds_file.pages:
            for obj in page.objects:
                if not dds.ObjectType.is_plot(obj):
                    continue
                for trace in obj.traces:
                    trace_expressions.append(str(trace.expression))
                    for marker in trace.markers:
                        markers.append(
                            {
                                "name": marker.name,
                                "independent_value": str(marker.indep_value),
                                "dependent_value": str(marker.dep_value),
                            }
                        )
        descriptor_count = len(dds_file.windows)
    finally:
        dds.close_dds_file(dds_file)

    expected_dataset_path = Path(expected_dataset).resolve() if expected_dataset else None
    dataset_matches = (
        None
        if expected_dataset_path is None
        else default_dataset_path == expected_dataset_path
    )
    marker_matches = (
        None
        if expected_marker is None
        else any(marker["name"] == expected_marker for marker in markers)
    )
    reload_pass = bool(
        page_names
        and trace_expressions
        and (dataset_matches is not False)
        and (marker_matches is not False)
    )
    return {
        "dds": str(source),
        "default_dataset": str(default_dataset_path),
        "expected_dataset": str(expected_dataset_path) if expected_dataset_path else None,
        "dataset_binding_matches": dataset_matches,
        "pages": page_names,
        "trace_expressions": trace_expressions,
        "markers": markers,
        "expected_marker": expected_marker,
        "marker_matches": marker_matches,
        **_headless_window_evidence(descriptor_count, gui_required=gui_required),
        "descriptor_reload_pass": reload_pass,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--title", default="ADS Simulation Result")
    parser.add_argument("--marker-name")
    parser.add_argument("--marker-value")
    parser.add_argument("--equation")
    parser.add_argument("--note")
    parser.add_argument("--png", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument(
        "--require-visible-gui",
        action="store_true",
        help="Record the visible GUI gate as not verified by this headless script",
    )
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--status-output", type=Path)
    args = parser.parse_args()

    status = base_status("create_dds")
    status["dataset"] = str(args.dataset.resolve())
    try:
        status["metrics"] = create_data_display(
            args.dataset,
            args.output,
            trace_expression=args.trace,
            title=args.title,
            marker_name=args.marker_name,
            marker_value=args.marker_value,
            equation=args.equation,
            note=args.note,
            png_path=args.png,
            pdf_path=args.pdf,
            replace=args.replace,
            gui_required=args.require_visible_gui,
        )
        status["status"] = "ok"
        status["return_code"] = 0
    except Exception as exc:
        status["status"] = "failed"
        status["return_code"] = 2
        status["fatal_errors"].append(f"{type(exc).__name__}: {exc}")
    if args.status_output:
        write_json(args.status_output, status)
    print_json(status)
    return int(status["return_code"])


if __name__ == "__main__":
    raise SystemExit(main())
