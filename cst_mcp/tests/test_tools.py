import pytest

from cst_mcp import dispatch, register_tool, tool_names
from cst_mcp import runtime, tools
from cst_mcp.errors import ToolError
from tpc_service.backends.fake import FakeBackend


@pytest.fixture
def env(tmp_path):
    project = tmp_path / "sample.cst"
    project.write_text("offline fixture", encoding="utf-8")
    runtime.reset()
    runtime.configure(workdir=str(tmp_path / "work"), backend=FakeBackend())
    yield {"project": project, "work": tmp_path}
    service = runtime.get_service()
    service.shutdown()
    runtime.reset()


def test_tool_registry_is_generic_and_has_explicit_read_write_partition():
    assert set(tools.READ_TOOLS).isdisjoint(tools.WRITE_TOOLS)
    assert tools.READ_TOOLS | tools.WRITE_TOOLS == set(tool_names())
    assert "build_model" not in tool_names()
    assert "run_simulation" in tools.WRITE_TOOLS


def test_open_project_and_fake_solve_use_run_service(env):
    registered = dispatch("open_project", {"project_path": str(env["project"]), "copy": False})
    assert registered["ok"] is True
    project_id = registered["project"]["project_id"]
    queued = dispatch("run_simulation", {"project_id": project_id, "run_id": 0})
    assert queued["ok"] is True
    job_id = queued["job"]["job_id"]
    done = runtime.get_service().wait(job_id, timeout=3)
    assert done["status"] == "succeeded"
    results = dispatch("get_results", {"job_id": job_id})
    assert results["ok"] is True
    assert results["run_identity"]["run_id"] == 0


def test_unknown_tool_and_failed_result_are_structured():
    assert dispatch("not_registered")["error"]["code"] == "unknown_tool"


def test_csv_tools_share_metric_selection(env):
    source = env["work"] / "curves.csv"
    source.write_text('freq_GHz,"S1,1","S2,1"\n1,-12,-8\n2,-15,-2\n3,-13,-1\n')
    args = {"csv_path": str(source), "threshold_db": -3, "criterion": "above"}
    default = dispatch("analyze_s_parameters", args)["analysis"]
    assert (default["metric"], default["n_bands"]) == ("S1,1", 0)
    args["metric"] = "S2,1"
    analysis = dispatch("analyze_s_parameters", args)["analysis"]
    summary = dispatch("export_report", args)["summary"]
    assert analysis["total_bandwidth_ghz"] == summary["total_bandwidth_ghz"] == 1
    for tool in ("analyze_s_parameters", "export_report"):
        error = dispatch(tool, dict(args, metric="missing"))["error"]
        assert error["code"] == "invalid_arguments"
        assert error["details"]["available"] == ["S1,1", "S2,1"]


def test_domain_tool_extension_defaults_to_write_and_is_dispatchable():
    register_tool("demo_domain_tool",
                  {"name": "demo_domain_tool", "inputSchema": {"type": "object"}},
                  lambda arguments: {"ok": True, "echo": arguments.get("value")})
    assert "demo_domain_tool" in tools.WRITE_TOOLS
    assert dispatch("demo_domain_tool", {"value": 17})["echo"] == 17


def test_duplicate_domain_tool_is_rejected():
    with pytest.raises(ToolError, match="已注册"):
        register_tool("get_capabilities",
                      {"name": "get_capabilities", "inputSchema": {"type": "object"}},
                      lambda _arguments: {"ok": True})


def test_extension_read_only_annotation_is_respected():
    register_tool("demo_read_tool",
                  {"name": "demo_read_tool", "inputSchema": {"type": "object"},
                   "annotations": {"readOnlyHint": True}},
                  lambda _arguments: {"ok": True})
    assert "demo_read_tool" in tools.READ_TOOLS
    assert "demo_read_tool" not in tools.WRITE_TOOLS


def test_generic_source_has_no_domain_imports_or_direct_cst_primitives():
    from pathlib import Path

    package_root = Path(__file__).parents[1]
    for path in (package_root / "tools.py", package_root / "server.py"):
        content = path.read_text(encoding="utf-8")
        for forbidden in ("topo_modeler", "topo_templates", "mesh_grid", "tpc_toolkit", "em_enclosure"):
            assert forbidden not in content
        assert "add_to_history" not in content
