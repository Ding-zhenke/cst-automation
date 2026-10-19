"""Explicit Design Studio routes running exclusively on RunService's worker."""
import logging
import json
from pathlib import Path
from uuid import uuid4

from cst_solver.circuit.adapter import CircuitError
from tpc_service.backends.base import ok_result, fail_result, artifact


def contained(root, path):
    root = Path(root).resolve()
    path = (root / Path(path)).resolve()
    if path != root and root not in path.parents:
        raise CircuitError("circuit_spec_invalid", "Path must remain inside service workdir", path=str(path))
    return path


def register_circuit_handlers(service, *, replace=False, app_factory=None):
    """Register opt-in circuit routes. app_factory is an explicit SDK boundary."""
    if app_factory is None:
        def app_factory(path):
            from cst_solver import setup
            return setup(path)

    allowed = {"build": {"configure", "inspect", "read_results", "package"},
               "solve": {"run_task"}, "study": {"parameter_sequence"}}

    def handle(*, project, params, job, backend):
        app = None
        try:
            operation = params.get("operation")
            if operation not in allowed.get(job["kind"], set()):
                raise CircuitError("circuit_spec_invalid", "Unknown kind/operation combination")
            path = contained(service.workdir, project["path"])
            if operation == "configure":
                from cst_automation.circuit_schema import validate_circuit_spec
                validate_circuit_spec(params.get("spec"))
            if operation in ("read_results", "package"):
                contained(service.workdir, params["destination"])
            if operation in ("run_task", "parameter_sequence"):
                if not isinstance(params.get("task_name"), str) or not params["task_name"] or params.get("mode") not in ("network", "transient_cosim"):
                    raise CircuitError("circuit_spec_invalid", "Explicit task_name and valid mode required")
                if operation == "run_task" and not params.get("expected_results"):
                    raise CircuitError("circuit_spec_invalid", "Required result paths/run IDs must be explicit")
            if operation == "read_results":
                from cst_solver.circuit.results import CircuitResult
                dest = contained(service.workdir, params["destination"])
                report = CircuitResult(str(path)).export_csv(params["tree_path"], str(dest), run_id=params["run_id"])
                return ok_result(saved=True, result_summary=report["metadata"], artifacts=[artifact(p) for p in report["artifacts"]])
            app = app_factory(str(path))
            if getattr(backend, "dialog_monitoring", False):
                pid = getattr(getattr(app, "project", None), "pid", None)
                backend.dialog_pid = pid if type(pid) is int else None
            api = app.circuit
            if operation == "inspect":
                return ok_result(saved=False, result_summary={"circuit_readback": api.inspect(), "solver_verified": False})
            if operation == "configure":
                try:
                    report = api.apply(params["spec"])
                except CircuitError as exc:
                    if exc.code != "circuit_build_partial":
                        raise
                    token = uuid4().hex
                    partial = {"stage": exc.details.get("stage", "apply"), "error": str(exc), "saved": False}
                    try:
                        app.save()
                        partial["saved"] = True
                    except Exception as save_error:
                        partial["save_error"] = str(save_error)
                    try: partial["readback"] = api.inspect()
                    except Exception as read_error: partial["readback_error"] = str(read_error)
                    try: partial["messages"] = [str(m) for m in app.get_messages()]
                    except Exception as message_error: partial["message_error"] = str(message_error)
                    audit = path.parent / path.stem / "circuit_failures" / (token + ".json")
                    audit.parent.mkdir(parents=True, exist_ok=True)
                    audit.write_text(json.dumps(partial, ensure_ascii=False, indent=2), encoding="utf-8")
                    return fail_result(exc.code, str(exc), saved=partial["saved"], run_identity={"run_token": token},
                                       result_summary={"partial_build": partial}, artifacts=[artifact(str(audit), kind="failure_audit"), artifact(str(path), kind="partial_project")])
                app.save()
                return ok_result(saved=True, result_summary=report, artifacts=[artifact(str(path), kind="project")])
            if operation == "package":
                dest = contained(service.workdir, params["destination"])
                report = api.bundle(str(dest))
                return fail_result("circuit_result_unverified", "Copies staged; live link relocation/reopen is pending", saved=False,
                                   result_summary=report, artifacts=[artifact(p) for p in report["artifacts"]])
            if operation == "parameter_sequence":
                points = params.get("points", [])
                if not isinstance(points, list) or not 1 <= len(points) <= 100:
                    raise CircuitError("circuit_spec_invalid", "Parameter sequence requires 1..100 explicit points")
                reports = []
                for point in points:
                    api.set_properties(point["block_name"], point["properties"], units=point["units"])
                    result = api.run_checked(params["task_name"], mode=params["mode"], expected_results=point["expected_results"], reuse="never")
                    reports.append(result)
                    if result["status"] != "succeeded":
                        return _outcome(result, reports)
                return ok_result(saved=True, result_summary={"points": reports})
            result = api.run_checked(params["task_name"], mode=params["mode"], expected_results=params["expected_results"],
                                     reuse=params.get("reuse", "never"), note=params.get("note", ""))
            return _outcome(result)
        except CircuitError as exc:
            return fail_result(exc.code, str(exc), **exc.details)
        except (KeyError, TypeError, ValueError) as exc:
            return fail_result("circuit_spec_invalid", f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            return fail_result("backend_failed", f"{type(exc).__name__}: {exc}")
        finally:
            if app is not None:
                try:
                    app.close()  # Existing attach ownership policy is preserved.
                except Exception:
                    logging.getLogger(__name__).exception("Circuit session cleanup failed; preserving operation evidence")

    service.register_workflow("circuit", {kind: handle for kind in allowed}, replace=replace)


def _outcome(result, sequence=None):
    common = {"saved": result.get("saved", False),
              "run_identity": {"run_token": result["run_token"], "task_name": result.get("task_name"), "mode": result.get("mode")},
              "result_summary": {"circuit_outcome": result, "points": sequence},
              "artifacts": [artifact(result["audit_path"], kind="run_audit")] if result.get("audit_path") else []}
    if result["status"] == "succeeded":
        return ok_result(**common)
    error = (result.get("errors") or [{}])[0]
    return fail_result(error.get("code", "circuit_result_unverified"), error.get("message", "Circuit run not verified"), **common)
