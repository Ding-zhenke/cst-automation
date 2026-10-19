from __future__ import annotations

import subprocess
import sys

import pytest


def test_offline_imports_do_not_load_cst_or_domain_packages():
    code = r'''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    blocked = ("cst", "mesh_grid", "topo_modeler", "topo_templates", "em_enclosure", "tpc_toolkit")
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in self.blocked):
            raise RuntimeError("forbidden import: " + fullname)
sys.meta_path.insert(0, Block())
import cst_solver, tpc_service, cst_mcp, cst_automation
assert "cst" not in sys.modules
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_curve_and_s2p_compatibility_entrypoints_exist():
    from cst_automation.curves import contiguous_bands, find_resonances
    from cst_automation.s2p import read_s2p_groups

    assert callable(contiguous_bands)
    assert callable(find_resonances)
    assert callable(read_s2p_groups)


def test_run_service_domain_handler_registration(tmp_path):
    from tpc_service import RunService, ServiceError
    from tpc_service.backends.base import ok_result
    from tpc_service.backends.fake import FakeBackend

    service = RunService(str(tmp_path), backend=FakeBackend())
    calls = []
    project_path = tmp_path / "test.cst"
    project_path.write_text("offline fixture", encoding="utf-8")

    def build(*, project, params, job, backend):
        calls.append((project, params, job, backend))
        return ok_result(saved=True, result_summary={"handled": True})

    service.register_handler("build", build)
    with pytest.raises(ServiceError) as duplicate:
        service.register_handler("build", build)
    assert duplicate.value.code == "domain_handler_exists"
    job = service.submit("build", project_path=str(project_path), params={"x": 3}, copy=False)
    completed = service.wait(job["job_id"], timeout=2)
    assert completed["status"] == "succeeded"
    assert calls and calls[0][1]["x"] == 3
    service.shutdown()


def test_run_service_reports_missing_domain_handler(tmp_path):
    from tpc_service import RunService, ServiceError
    from tpc_service.backends.cst_backend import CstBackend

    backend = CstBackend()
    backend.dialog_monitoring = False
    service = RunService(str(tmp_path), backend=backend)
    project_path = tmp_path / "model.cst"
    project_path.write_text("offline fixture", encoding="utf-8")
    job = service.submit("build", project_path=str(project_path), copy=False)
    completed = service.wait(job["job_id"], timeout=2)
    assert completed["status"] == "failed"
    assert completed["error"]["code"] == "domain_handler_missing"
    service.shutdown()


def test_cst_backend_does_not_implicitly_import_tpc():
    code = r'''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    blocked = ("topo_modeler", "topo_templates", "mesh_grid", "tpc_toolkit")
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in self.blocked):
            raise RuntimeError("forbidden import: " + fullname)
from tpc_service.backends.cst_backend import CstBackend
sys.meta_path.insert(0, Block())
backend = CstBackend()
assert backend.name == "cst"
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_mcp_has_dynamic_domain_tool_registration():
    from cst_mcp import dispatch, register_tool, tool_names

    register_tool("example_domain", {"name": "example_domain", "inputSchema": {"type": "object"}},
                  lambda arguments: {"ok": True, "echo": arguments.get("value")})
    assert "example_domain" in tool_names()
    assert dispatch("example_domain", {"value": 9})["echo"] == 9
