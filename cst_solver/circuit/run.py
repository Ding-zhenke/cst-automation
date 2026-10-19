"""Task-level contract. Native submission alone cannot prove solver completion."""
import json
from pathlib import Path
from uuid import uuid4

from .adapter import CircuitError
from .results import task_result_path
from .evidence import information_only


def run_checked(api, task_name, *, mode, expected_results, reuse="never", note=""):
    token = uuid4().hex
    out = {"run_token": token, "task_name": task_name, "mode": mode, "status": "unverified", "errors": [],
           "saved": False, "messages": [], "expected_results": [], "execution_evidence": {}, "note": note, "cache": {"reused": False}}
    try:
        path = Path(api.app.cst_file.filename()).resolve()
        if not path.is_file():
            raise ValueError("Project file does not exist")
    except Exception as exc:
        out["status"] = "failed"
        out["audit_path"] = None
        out["errors"].append({"code": "circuit_unavailable", "message": f"A saved project is required: {exc}"})
        return out
    audit = path.parent / path.stem / "circuit_runs" / (token + ".json")
    def persist():
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if mode not in ("network", "transient_cosim") or reuse not in ("never", "verified"):
            raise CircuitError("circuit_spec_invalid", "Invalid mode or reuse policy")
        if not isinstance(task_name, str) or not task_name or not isinstance(expected_results, list) or not expected_results:
            raise CircuitError("circuit_spec_invalid", "Target task and required expected_results must be explicit")
        for expected in expected_results:
            if not isinstance(expected, dict) or not isinstance(expected.get("tree_path"), str) or not task_result_path(expected["tree_path"], task_name) or type(expected.get("run_id")) is not int:
                raise CircuitError("circuit_spec_invalid", "Each expected result needs target task path and explicit integer run_id")
        validation = api.validate(task_name=task_name)
        if not validation["ok"]:
            raise CircuitError("circuit_dependency_missing", "Missing circuit dependencies", validation=validation)
        task = validation["task"]
        actual_cosim = task["type"] == "transient" and task["properties"].get("circuit simulator", "").lower() == "cosimulation"
        if actual_cosim != (mode == "transient_cosim"):
            raise CircuitError("circuit_mode_unsupported", "Requested mode differs from actual task properties")
        out["task_readback"] = task
        out["preflight"] = validation
        if reuse == "verified":
            out["errors"].append({"code": "circuit_result_unverified", "message": "Verified cache provenance is not available; no task was executed"})
        else:
            out["stage"] = "submitting_target_task"
            persist()
            api.adapter.update_task(task_name)
            api.app.save()
            out["saved"] = True
            out["messages"] = list(api.app.get_messages())
            out["stage"] = "saved_messages_captured"
            persist()
            proof = api.adapter.execution_evidence(task_name, token)
            out["execution_evidence"] = proof
            valid = (proof.get("completed") is True and proof.get("task_name") == task_name and proof.get("run_token") == token
                     and proof.get("mode") == mode and (mode != "transient_cosim" or proof.get("em_completed") is True))
            observed = {(r.get("tree_path"), r.get("run_id")) for r in proof.get("circuit_runs", [])}
            valid = valid and all((r["tree_path"], r["run_id"]) in observed for r in expected_results)
            if mode == "transient_cosim":
                em_runs = proof.get("em_runs", [])
                valid = valid and bool(em_runs) and all(r.get("domain") == "3d" and type(r.get("run_id")) is int for r in em_runs)
            if not valid:
                out["errors"].append({"code": "circuit_result_unverified", "message": "Target task completion / two-sided run identity not proven"})
            else:
                from .results import CircuitResult
                reader = CircuitResult(str(path))
                for expected in expected_results:
                    curve = reader.read_curve(expected["tree_path"], run_id=expected["run_id"])
                    if expected.get("parameters") is not None and expected["parameters"] != curve["parameters"]:
                        raise CircuitError("circuit_result_unverified", "Result parameters differ from requested input")
                    out["expected_results"].append({k: v for k, v in curve.items() if k not in ("x", "y")})
                if information_only(out["messages"]):
                    out["status"] = "succeeded"
                else:
                    out["errors"].append({"code": "circuit_result_unverified", "message": "CST messages require review"})
    except CircuitError as exc:
        out["status"] = "unverified" if exc.code == "circuit_result_unverified" else "failed"
        out["errors"].append({"code": exc.code, "message": str(exc), "details": exc.details})
    except Exception as exc:
        out["status"] = "failed"
        out["errors"].append({"code": "circuit_result_read_failed", "message": f"{type(exc).__name__}: {exc}"})
    out["audit_path"] = str(audit)
    out["stage"] = "finished"
    persist()
    return out
