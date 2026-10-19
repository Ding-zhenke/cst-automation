"""Offline checks for the generic CST backend; no CST process is started."""

import subprocess
import sys

from tpc_service.backends.cst_backend import CstBackend


def test_backend_import_isolated_from_cst_and_domain_packages():
    code = r'''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    blocked = ("cst", "topo_modeler", "topo_templates", "mesh_grid", "tpc_toolkit", "em_enclosure")
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in self.blocked):
            raise RuntimeError("forbidden import: " + fullname)
from tpc_service.backends.cst_backend import CstBackend
sys.meta_path.insert(0, Block())
assert CstBackend().name == "cst"
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_build_and_study_require_explicit_domain_handlers():
    backend = CstBackend()
    for kind, result in (("build", backend.build(project={}, params={}, job={})),
                         ("study", backend.study(project={}, params={}, job={}))):
        assert result["ok"] is False
        assert result["error"]["code"] == "domain_handler_missing"
        assert "register_handler" in result["error"]["message"]
        assert result["error"]["details"]["kind"] == kind


def test_solve_reports_missing_project_without_loading_cst(tmp_path):
    result = CstBackend().solve(project={"path": str(tmp_path / "missing.cst")},
                                params={}, job={})
    assert result["ok"] is False
    assert result["error"]["code"] == "project_not_found"
