"""Task-level contract. Native submission alone cannot prove solver completion."""
import json
import hashlib
from pathlib import Path
from uuid import uuid4

from .adapter import CircuitError
from .results import task_result_path
from .evidence import information_only


def _disk_observation(path):
    try:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return {'sha256': digest.hexdigest(), 'error': None}
    except OSError as exc:
        return {'sha256': None, 'error': f'{type(exc).__name__}: {exc}'}


def _log_observation(path):
    try:
        return path.read_bytes(), None
    except OSError as exc:
        return None, f'{type(exc).__name__}: {exc}'


def run_checked(api, task_name, *, mode, expected_results, reuse="never", note="", result_selectors=None):
    token = uuid4().hex
    out = {"run_token": token, "task_name": task_name, "mode": mode, "status": "unverified", "errors": [],
           "saved": False, "submitted": False, "execution_returned": False, "saved_digest": None,
           "update_call_state": "not_called", "failure_stage": None,
           "messages": [], "expected_results": [], "execution_evidence": {}, "note": note, "cache": {"reused": False}}
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
    out['project'] = str(path)
    def persist():
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if mode not in ("network", "transient_cosim") or reuse not in ("never", "verified"):
            raise CircuitError("circuit_spec_invalid", "Invalid mode or reuse policy")
        selectors_valid = (result_selectors == ['11','12','21','22'] and mode == 'network' and reuse == 'never'
                           and expected_results == [])
        if (result_selectors is not None and not selectors_valid):
            raise CircuitError('circuit_spec_invalid', 'Exactly four ordered SP selectors and no explicit paths required')
        if not isinstance(task_name, str) or not task_name or not isinstance(expected_results, list) or (not expected_results and not selectors_valid):
            raise CircuitError("circuit_spec_invalid", "Target task and required expected_results must be explicit")
        for expected in expected_results:
            if not isinstance(expected, dict) or not isinstance(expected.get("tree_path"), str) or not task_result_path(expected["tree_path"], task_name) or type(expected.get("run_id")) is not int:
                raise CircuitError("circuit_spec_invalid", "Each expected result needs target task path and explicit integer run_id")
        validation = api.validate(task_name=task_name)
        if not validation["ok"]:
            raise CircuitError("circuit_dependency_missing", "Missing circuit dependencies", validation=validation)
        task = validation["task"]
        if selectors_valid and str(task.get('type','')).casefold() != 's-parameters':
            raise CircuitError('circuit_mode_unsupported', 'SP selectors require an S-parameter task')
        actual_cosim = task["type"] == "transient" and task["properties"].get("circuit simulator", "").lower() == "cosimulation"
        if actual_cosim != (mode == "transient_cosim"):
            raise CircuitError("circuit_mode_unsupported", "Requested mode differs from actual task properties")
        out["task_readback"] = task
        out["preflight"] = validation
        if reuse == "verified":
            out["errors"].append({"code": "circuit_result_unverified", "message": "Verified cache provenance is not available; no task was executed"})
        else:
            out["stage"] = "submitting_target_task"
            logfile = path.with_suffix('') / 'Result' / 'DS' / 'Model.log'
            before_log, before_log_error = _log_observation(logfile)
            out['disk_before_update'] = _disk_observation(path)
            out['submitted'] = True
            out['update_call_state'] = 'calling'
            persist()
            try:
                api.adapter.update_task(task_name)
            except Exception as exc:
                out['update_call_state'] = 'raised'
                out['failure_stage'] = 'update_task'
                out['save_policy'] = 'deferred_until_idle'
                after_log, after_log_error = _log_observation(logfile)
                comparable = before_log is not None and after_log is not None
                appended = comparable and after_log.startswith(before_log)
                out['update_failure_evidence'] = {
                    'log_path': str(logfile), 'before_read_error': before_log_error,
                    'after_read_error': after_log_error,
                    'log_changed': before_log != after_log if comparable else None,
                    'before_sha256': hashlib.sha256(before_log).hexdigest() if before_log is not None else None,
                    'after_sha256': hashlib.sha256(after_log).hexdigest() if after_log is not None else None,
                    'new_log_text': after_log[len(before_log):].decode('utf-8-sig', errors='replace') if appended else None,
                    'log_replaced': not appended if comparable else None,
                    'disk_after_error': _disk_observation(path), 'idle_verified': False}
                raise CircuitError('circuit_task_update_failed', 'Task update raised; partial state requires idle review',
                                   exception_type=type(exc).__name__, original_message=str(exc),
                                   original_code=exc.code if isinstance(exc, CircuitError) else None,
                                   original_details=exc.details if isinstance(exc, CircuitError) else None) from exc
            out['update_call_state'] = 'returned'
            out['execution_returned'] = True
            api.app.save()
            out["saved"] = True
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            out['saved_digest'] = digest.hexdigest()
            out["messages"] = list(api.app.get_messages())
            out["stage"] = "saved_messages_captured"
            persist()
            proof = api.adapter.execution_evidence(task_name, token)
            out["execution_evidence"] = proof
            after_dependencies = api.inspect_dependencies()
            def external_files(manifest):
                return {str(Path(f['path']).resolve()): f.get('sha256') for f in manifest['files']
                        if Path(f['path']).resolve() != path}
            before_files, after_files = external_files(validation['dependencies']), external_files(after_dependencies)
            dependencies_unchanged = (after_dependencies.get('complete') is True and not after_dependencies.get('unknown')
                                      and before_files == after_files and all(before_files.values()))
            proof['external_dependencies_unchanged'] = bool(dependencies_unchanged)
            out['dependencies_after'] = after_dependencies
            if not dependencies_unchanged:
                out['errors'].append({'code': 'circuit_result_unverified',
                                      'message': 'External model dependencies changed or became unreadable during execution'})
            valid = (proof.get("completed") is True and proof.get("task_name") == task_name and proof.get("run_token") == token
                     and proof.get("mode") == mode and dependencies_unchanged
                     and (mode != "transient_cosim" or proof.get("em_completed") is True))
            observed = {(r.get("tree_path"), r.get("run_id")) for r in proof.get("circuit_runs", [])}
            selected = expected_results
            if selectors_valid:
                selected=[]
                for key in result_selectors:
                    suffix='\\S-Parameters\\S'+key[0]+','+key[1]
                    paths=sorted({path for path,rid in observed if isinstance(path,str) and rid==0
                                  and task_result_path(path,task_name) and path.endswith(suffix)})
                    if len(paths)!=1:
                        valid=False
                        break
                    selected.append({'tree_path':paths[0],'run_id':0})
                out['resolved_result_paths']={k:v['tree_path'] for k,v in zip(result_selectors,selected)}
                valid=valid and len(selected)==4
            valid = valid and all((r["tree_path"], r["run_id"]) in observed for r in selected)
            if mode == "transient_cosim":
                em_runs = proof.get("em_runs", [])
                valid = valid and bool(em_runs) and all(r.get("domain") == "3d" and type(r.get("run_id")) is int for r in em_runs)
            if not valid:
                out["errors"].append({"code": "circuit_result_unverified", "message": "Target task completion / two-sided run identity not proven"})
            else:
                from .results import CircuitResult
                reader = CircuitResult(str(path))
                for expected in selected:
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
