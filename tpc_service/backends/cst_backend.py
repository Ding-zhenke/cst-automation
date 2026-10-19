from __future__ import annotations

"""Generic CST backend for operations on existing project files.

This module imports the CST API only inside ``solve``. Domain-specific build
and study behavior belongs in an explicitly registered handler.
"""

import os
from typing import Any, Dict, List

from tpc_service.backends.base import Backend, artifact, fail_result, ok_result

__all__ = ["CstBackend"]


def _missing_domain_handler(kind: str) -> Dict[str, Any]:
    return fail_result(
        "domain_handler_missing",
        f"任务 {kind!r} 需要领域适配器。请在提交任务前调用 "
        "RunService.register_handler(kind, handler) 注册实现。",
        kind=kind,
        action="register a domain handler with RunService.register_handler",
    )


class CstBackend(Backend):
    """Run general CST operations without importing any domain package."""

    name = "cst"
    dialog_monitoring = True
    dialog_monitoring = True

    def __init__(self, *, dialog_poll: float = 1.0,
                 dialog_timeout: float | None = None):
        self.dialog_poll = float(dialog_poll)
        self.dialog_timeout = dialog_timeout
        self.dialog_pid = None

    def prepare_dialog_monitor(self) -> None:
        self.dialog_pid = None

    def _track_dialog_target(self, app: Any) -> None:
        from cst_solver.environment import environment_pid
        self.dialog_pid = environment_pid(getattr(app, "project", None))

    def build(self, *, project, params, job):
        """Build rules are supplied by the calling domain package."""
        return _missing_domain_handler("build")

    def study(self, *, project, params, job):
        """Parameter studies are supplied by the calling domain package."""
        return _missing_domain_handler("study")

    def solve(self, *, project, params, job):
        """Solve an existing CST project, save it, and report run identity.

        Result extraction is deliberately separate: callers can use
        ``cst_solver.Result`` after this method succeeds. A successful solver
        contract is not evidence that a particular device meets a performance
        target.
        """
        from cst_solver import setup

        self.dialog_pid = None
        path = str(project.get("path") or "")
        if not os.path.isfile(path):
            return fail_result("project_not_found", f"工程不存在：{path}", path=path)
        app = None
        log: List[str] = []
        try:
            app = setup(path)
            self._track_dialog_target(app)
            outcome = app.run_checked(project_path=path,
                                      note=str(params.get("note", "")))
            log.append(f"运行契约：status={outcome.get('status')}")
            log.extend(str(message) for message in outcome.get("messages", []))
            if outcome.get("status") != "succeeded":
                first = (outcome.get("errors") or [{}])[0]
                return fail_result(
                    first.get("code", "backend_failed"),
                    f"求解未确认成功（status={outcome.get('status')}）："
                    f"{first.get('message', '')}",
                    retryable=True,
                    log=log,
                    run_identity={"run_token": outcome.get("run_token")},
                )
            app.save(path)
            log.append(f"结果已保存：{path}")
            return ok_result(
                log=log,
                artifacts=[artifact(path, kind="project", note="CST 求解后已保存")],
                run_identity={"run_token": outcome.get("run_token"),
                              "run_id": params.get("run_id", 0)},
                result_summary={"solver_status": "succeeded",
                                "result_readback": "not_requested"},
                saved=True,
            )
        except Exception as exc:  # noqa: BLE001 - reported as structured task failure
            return fail_result("backend_failed",
                               f"求解过程异常：{type(exc).__name__}: {exc}",
                               retryable=True, log=log)
        finally:
            if app is not None:
                try:
                    app.close()
                except Exception as exc:  # noqa: BLE001
                    log.append(f"关闭会话失败（不掩盖求解结果）：{exc!r}")

    def close_project(self, *, project, save=True):
        """No CST session is retained by the generic backend instance."""
        return None
