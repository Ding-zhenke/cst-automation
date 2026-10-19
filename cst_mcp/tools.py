"""Generic CST task and S-parameter tools exposed through MCP.

Domain packages may register their own tools. This module never imports a
domain package and never sends commands to CST directly.
"""

from typing import Any, Callable, Dict, List, Optional

from cst_mcp.errors import ToolError, error_payload, tool_payload

__all__ = ["TOOL_SPECS", "HANDLERS", "READ_TOOLS", "WRITE_TOOLS",
           "tool_names", "register_tool", "dispatch"]


def _spec(name: str, description: str, properties: Dict[str, Any],
          required: Optional[List[str]] = None, *, read_only: bool = True) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties,
                        "required": list(required or {}),
                        "additionalProperties": False},
        "annotations": {"readOnlyHint": read_only},
    }


TOOL_SPECS: List[Dict[str, Any]] = [
    _spec("get_capabilities", "Describe installed CST and available runtime capabilities.", {}),
    _spec("open_project", "Register an existing CST project with the task service.",
          {"project_path": {"type": "string"}, "copy": {"type": "boolean", "default": True}},
          ["project_path"], read_only=False),
    _spec("get_project_state", "List registered projects and recent task records.",
          {"project_id": {"type": "string"}}),
    _spec("run_simulation", "Queue a CST solve for an existing project.",
          {"project_id": {"type": "string"}, "project_path": {"type": "string"},
           "run_id": {"type": "integer"}, "note": {"type": "string"}},
          read_only=False),
    _spec("get_job_status", "Read job state, errors, artifacts, and runtime diagnostics.",
          {"job_id": {"type": "string"}}, ["job_id"]),
    _spec("get_results", "Read the saved summary and artifact references for a completed job.",
          {"job_id": {"type": "string"}}, ["job_id"]),
    _spec("close_project", "Release a registered project; only service-owned sessions are closed.",
          {"project_id": {"type": "string"}, "save": {"type": "boolean", "default": True}},
          ["project_id"], read_only=False),
    _spec("analyze_s_parameters", "Analyze an S-parameter CSV using shared band and resonance rules.",
          {"csv_path": {"type": "string"}, "metric": {"type": "string"},
           "threshold_db": {"type": "number"}, "criterion": {"type": "string", "enum": ["below", "above"]},
           "max_gap_ghz": {"type": "number"}, "resonance_kind": {"type": "string", "enum": ["min", "max"]}},
          ["csv_path", "threshold_db"]),
    _spec("export_report", "Export a self-contained report and CSV from an S-parameter CSV.",
          {"csv_path": {"type": "string"}, "threshold_db": {"type": "number"},
           "metric": {"type": "string"}, "criterion": {"type": "string", "enum": ["below", "above"]},
           "formats": {"type": "array", "items": {"type": "string", "enum": ["html", "csv"]}},
           "title": {"type": "string"}}, ["csv_path", "threshold_db"], read_only=False),
]

HANDLERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}


def tool_names() -> List[str]:
    return [spec["name"] for spec in TOOL_SPECS]


def register_tool(name: str, definition: Dict[str, Any],
                  handler: Callable[[Dict[str, Any]], Dict[str, Any]], *,
                  replace: bool = False) -> None:
    """Register a domain tool explicitly in this MCP process.

    Unannotated extension tools are treated as writes for safety. Set
    ``definition['annotations']['readOnlyHint'] = True`` for read-only tools.
    """
    if not isinstance(definition, dict) or definition.get("name") != name:
        raise ToolError("invalid_tool_definition", "definition.name 必须与注册名一致", name=name)
    if not isinstance(definition.get("inputSchema"), dict):
        raise ToolError("invalid_tool_definition", "definition.inputSchema 必须是对象", name=name)
    if not callable(handler):
        raise ToolError("invalid_tool_handler", "MCP tool handler 必须可调用", name=name)
    if name in HANDLERS and not replace:
        raise ToolError("tool_exists", f"工具 {name!r} 已注册", name=name)
    copied = dict(definition)
    copied.setdefault("description", "")
    annotations = dict(copied.get("annotations") or {})
    annotations.setdefault("readOnlyHint", False)
    copied["annotations"] = annotations
    existing = next((i for i, spec in enumerate(TOOL_SPECS) if spec["name"] == name), None)
    if existing is None:
        TOOL_SPECS.append(copied)
    else:
        TOOL_SPECS[existing] = copied
    HANDLERS[name] = handler
    _refresh_partitions()


def _service():
    from cst_mcp.runtime import get_service
    return get_service()


def handle_get_capabilities(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cst_mcp.runtime import describe_runtime
    from cst_solver.environment import diagnose_environment

    return tool_payload({"runtime": describe_runtime(),
                         "cst_environment": diagnose_environment(probe=False),
                         "evidence": {"import": "offline-capable",
                                      "readback": "not tested by capability discovery",
                                      "solver": "not tested by capability discovery"}})


def handle_open_project(arguments: Dict[str, Any]) -> Dict[str, Any]:
    path = arguments.get("project_path")
    if not isinstance(path, str) or not path.strip():
        raise ToolError("invalid_arguments", "project_path 必须是非空路径")
    project = _service().open_project(path, copy=bool(arguments.get("copy", True)))
    return tool_payload({"project": project}, notes=[
        "登记工程不代表几何重建、结果读取或求解已验证。"])


def handle_get_project_state(arguments: Dict[str, Any]) -> Dict[str, Any]:
    service = _service()
    projects = service.projects()
    if arguments.get("project_id"):
        projects = [p for p in projects if p.get("project_id") == arguments["project_id"]]
    return tool_payload({"projects": projects, "jobs": service.list_jobs()[-50:],
                         "runtime": service.describe()})


def handle_run_simulation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    project_id, project_path = arguments.get("project_id"), arguments.get("project_path")
    if not project_id and not project_path:
        raise ToolError("missing_requirement", "请提供 project_id 或 project_path",
                        missing="project_id|project_path")
    job = _service().submit("solve", project_id=project_id, project_path=project_path,
                            params={"run_id": arguments.get("run_id", 0),
                                    "note": arguments.get("note", "")})
    return tool_payload({"job": job}, notes=["任务异步排队；成功状态需等待真实 solver 返回。"])


def handle_get_job_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    job_id = _required_string(arguments, "job_id")
    job = _service().get(job_id)
    notes = []
    diagnostics = job.get("runtime_diagnostics") or {}
    if diagnostics.get("attention_required"):
        notes.append("运行诊断要求处理：先读取弹窗正文、按钮与进程归属。")
    if job.get("status") == "interrupted":
        notes.append("任务已中断，不会自动重跑，也不得视作成功。")
    return tool_payload({"job": job}, notes=notes)


def handle_get_results(arguments: Dict[str, Any]) -> Dict[str, Any]:
    job_id = _required_string(arguments, "job_id")
    service = _service()
    job = service.get(job_id)
    if job.get("status") != "succeeded":
        error = job.get("error") or {}
        return error_payload(error.get("code", "job_not_succeeded"),
                             f"任务状态为 {job.get('status')}，没有可采信的结果摘要。",
                             job_id=job_id, status=job.get("status"), job_error=error)
    return tool_payload(service.result(job_id))


def handle_close_project(arguments: Dict[str, Any]) -> Dict[str, Any]:
    project_id = _required_string(arguments, "project_id")
    result = _service().close_project(project_id, save=bool(arguments.get("save", True)))
    return tool_payload(result, notes=[] if result.get("closed_session") else
                        ["外部会话只解除服务登记，没有被关闭。"])


def _load_analysis(arguments: Dict[str, Any]):
    from cst_mcp.analysis import _pick_column, analyze_series, read_series_csv

    path = arguments.get("csv_path")
    if not isinstance(path, str) or not path:
        raise ToolError("missing_requirement", "csv_path 必须指向已有 CSV", missing="csv_path")
    series = read_series_csv(path)
    metric = str(arguments.get("metric") or next(iter(series["columns"]), ""))
    if not metric:
        raise ToolError("analysis_failed", "CSV 中没有可分析的参数列", path=path)
    values = _pick_column(series, metric)
    threshold = arguments.get("threshold_db")
    if isinstance(threshold, bool) or not isinstance(threshold, (float, int)):
        raise ToolError("invalid_arguments", "threshold_db 必须是数值 (dB)")
    analysis = analyze_series(
        series["freqs"], values, metric=metric, threshold_db=float(threshold),
        criterion=str(arguments.get("criterion") or "below"),
        max_gap_ghz=arguments.get("max_gap_ghz"),
        resonance_kind=arguments.get("resonance_kind"),
        data_source={"kind": "csv", "path": series["path"]},
    )
    return series, analysis


def handle_analyze_s_parameters(arguments: Dict[str, Any]) -> Dict[str, Any]:
    _series, analysis = _load_analysis(arguments)
    return tool_payload({"analysis": analysis})


def handle_export_report(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from cst_mcp.reporting import export_report

    series, analysis = _load_analysis(arguments)
    service = _service()
    result = export_report(
        analysis=analysis, workdir=service.workdir,
        out_dir=str(arguments.get("out_dir") or service.workdir),
        title=str(arguments.get("title") or "S-parameter report"),
        formats=arguments.get("formats") or ("html", "csv"), series=series,
        meta={"backend": getattr(service.backend, "name", "unknown")},
    )
    return tool_payload(result)


def _required_string(arguments: Dict[str, Any], name: str) -> str:
    value = (arguments or {}).get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolError("invalid_arguments", f"{name} 必须是非空字符串", field=name)
    return value


def dispatch(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler is None:
        return error_payload("unknown_tool", f"未知工具 {name!r}；可用：{tool_names()}",
                             tool=name, available=tool_names())
    try:
        result = handler(dict(arguments or {}))
        return result if isinstance(result, dict) else tool_payload({"result": result})
    except ToolError as exc:
        return error_payload(exc.code, str(exc), retryable=exc.retryable, **exc.details)
    except Exception as exc:  # noqa: BLE001 - preserve structured client failures
        code = getattr(exc, "code", "tool_failed")
        details = dict(getattr(exc, "details", {}) or {})
        if code == "tool_failed":
            details["exception"] = f"{type(exc).__name__}: {exc}"
        return error_payload(str(code), str(exc), retryable=bool(getattr(exc, "retryable", False)),
                             tool=name, **details)


def _refresh_partitions() -> None:
    global READ_TOOLS, WRITE_TOOLS
    READ_TOOLS = {spec["name"] for spec in TOOL_SPECS
                  if (spec.get("annotations") or {}).get("readOnlyHint") is True}
    WRITE_TOOLS = set(HANDLERS) - READ_TOOLS


READ_TOOLS: set[str] = set()
WRITE_TOOLS: set[str] = set()
for _tool in TOOL_SPECS:
    HANDLERS[_tool["name"]] = globals()[f"handle_{_tool['name']}"]
_refresh_partitions()
