"""Opt-in circuit tools. Native operations are queued through RunService."""
from pathlib import Path
from uuid import uuid4

from .errors import ToolError, tool_payload, error_payload


def register_circuit_tools(*, replace=False, compose_handlers=False):
    from .tools import register_tool, _spec
    installed = set()

    def service():
        from .runtime import get_service
        from tpc_service.circuit import register_circuit_handlers
        current = get_service()
        if current not in installed:
            register_circuit_handlers(current, replace=compose_handlers)
            installed.add(current)
        return current

    def preview(arguments):
        from .runtime import describe_runtime
        from tpc_service.circuit import contained
        from cst_automation.circuit_preview import preview_circuit
        from cst_solver.circuit.adapter import CircuitError
        try:
            root = Path(describe_runtime()["workdir"])
            target = arguments.get("destination", str(root / "circuit-previews" / uuid4().hex))
            target = contained(root, root / target)
            return tool_payload(preview_circuit(arguments["spec"], str(target)))
        except (CircuitError, ValueError, KeyError) as exc:
            return error_payload(getattr(exc, "code", "circuit_spec_invalid"), str(exc))

    def queued(operation, kind, arguments):
        from cst_solver.circuit.adapter import CircuitError
        from tpc_service.errors import ServiceError
        try:
            if not arguments.get("project_id") and not arguments.get("project_path"):
                raise CircuitError("circuit_spec_invalid", "project_id or project_path required")
            params = {k: v for k, v in arguments.items() if k not in ("project_id", "project_path", "request_id")}
            params.update(workflow="circuit", operation=operation)
            job = service().submit(kind, project_id=arguments.get("project_id"), project_path=arguments.get("project_path"),
                                   request_id=arguments.get("request_id"), params=params)
            return tool_payload({"job": job})
        except (CircuitError, ServiceError) as exc:
            return error_payload(exc.code, str(exc))

    common = {"project_id": {"type": "string"}, "project_path": {"type": "string"}, "request_id": {"type": "string"}}
    definitions = [
        ("preview_circuit", "Validate circuit data and write offline preview inside workdir.", {"spec": {"type": "object"}, "destination": {"type": "string"}}, ["spec"], False, preview),
        ("inspect_circuit", "Queue read-only schematic inspection.", common, [], True, lambda a: queued("inspect", "build", a)),
        ("configure_circuit", "Queue schematic configuration and save.", dict(common, spec={"type": "object"}), ["spec"], False, lambda a: queued("configure", "build", a)),
        ('configure_circuit_transient_task', 'Queue unit-explicit transient settings and save without solving.',
         dict(common, task_name={'type':'string'}, settings={'type':'object'}, create={'type':'boolean'}),
         ['task_name','settings'], False, lambda a: queued('configure_transient_task','build',a)),
        ("run_circuit_task", "Queue one task; missing completion evidence remains unverified.",
         dict(common, task_name={"type": "string"}, mode={"type": "string", "enum": ["network", "transient_cosim"]},
              expected_results={"type": "array", "items": {"type": "object"}}, reuse={"type": "string", "enum": ["never", "verified"]}, note={"type": "string"}),
         ["task_name", "mode", "expected_results"], False, lambda a: queued("run_task", "solve", a)),
        ("read_circuit_results", "Queue saved schematic curve export with explicit run ID.",
         dict(common, tree_path={"type": "string"}, run_id={"type": "integer"}, destination={"type": "string"}),
         ["tree_path", "run_id", "destination"], False, lambda a: queued("read_results", "build", a)),
        ("package_circuit_project", "Queue dependency staging; portable status requires live relocation/readback.",
         dict(common, destination={"type": "string"}), ["destination"], False, lambda a: queued("package", "build", a)),
    ]
    for name, description, properties, required, read_only, handler in definitions:
        register_tool(name, _spec(name, description, properties, required, read_only=read_only), handler, replace=replace)
    return [d[0] for d in definitions]
