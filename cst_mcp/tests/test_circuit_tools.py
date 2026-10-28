import copy
import json
import sys
import os

import pytest

from cst_mcp import tools, runtime
from cst_mcp.circuit_tools import register_circuit_tools
from tpc_service.backends.fake import FakeBackend


@pytest.fixture
def circuit_tools(tmp_path):
    old_specs, old_handlers = copy.deepcopy(tools.TOOL_SPECS), dict(tools.HANDLERS)
    runtime.reset()
    runtime.configure(workdir=str(tmp_path), backend=FakeBackend())
    register_circuit_tools()
    yield tmp_path
    if runtime.service_ready(): runtime.get_service().shutdown()
    runtime.reset()
    tools.TOOL_SPECS[:] = old_specs
    tools.HANDLERS.clear()
    tools.HANDLERS.update(old_handlers)
    tools._refresh_partitions()


def test_registration_is_explicit_and_does_not_start_service(circuit_tools):
    assert not runtime.service_ready()
    assert "run_circuit_task" in tools.WRITE_TOOLS
    assert "inspect_circuit" in tools.READ_TOOLS
    assert "preview_circuit" in tools.WRITE_TOOLS


def test_preview_path_escape_rejected(circuit_tools):
    out = tools.dispatch("preview_circuit", {"spec": {"schema_version": 1}, "destination": str(circuit_tools.parent / "outside")})
    assert not out["ok"] and out["error"]["code"] == "circuit_spec_invalid"
    assert not (circuit_tools.parent / "outside").exists()


def test_preview_writes_bounded_offline_artifacts(circuit_tools):
    out = tools.dispatch("preview_circuit", {"spec": {"schema_version": 1}, "destination": str(circuit_tools / "preview")})
    assert out["ok"] and out["evidence"] == "offline_preview"
    assert (circuit_tools / "preview/circuit.svg").exists()


def test_run_tool_queues_selected_workflow_without_direct_sdk(circuit_tools):
    service = runtime.get_service()
    service.autostart = False
    path = circuit_tools / "p.cst"
    path.write_text("fixture")
    out = tools.dispatch("run_circuit_task", {"project_path": str(path), "task_name": "T", "mode": "transient_cosim", "expected_results": [{"tree_path": "T\\V", "run_id": 7}]})
    assert out["ok"]
    queued = service.get(out["job"]["job_id"])
    assert queued["params"]["workflow"] == "circuit"
    assert queued["params"]["operation"] == "run_task" and queued["params"]["task_name"] == "T"


def test_transient_configuration_tool_queues_build_without_running_solver(circuit_tools):
    service=runtime.get_service();service.autostart=False
    path=circuit_tools/'p.cst';path.write_text('fixture')
    settings={'mode':'transient_cosim','duration':{'value':40,'unit':'ns'}}
    out=tools.dispatch('configure_circuit_transient_task',{'project_path':str(path),'task_name':'TR','settings':settings,'create':True})
    assert out['ok']
    job=service.get(out['job']['job_id'])
    assert job['kind']=='build' and job['params']['operation']=='configure_transient_task'
    assert job['params']['settings']==settings and job['params']['create'] is True


@pytest.mark.parametrize('tool,operation,payload', [
    ('configure_circuit_steady_state_task', 'configure_steady_state_task', {'task_name': 'SS', 'settings': {'automatic_period': True}, 'create': True}),
    ('configure_circuit_task_ports', 'configure_task_ports', {'task_name': 'TR', 'ports': {'1': {
        'source_type': 'none', 'impedance': {'real': {'value': 50, 'unit': 'Ohm'}}}}}),
    ('configure_circuit_nonlinear_model', 'configure_nonlinear_model', {
        'block_name': 'D1', 'settings': {'kind': 'berkeley_diode'}, 'create': True}),
    ('stage_circuit_postprocessing_template', 'stage_postprocessing_template', {
        'template_source': 'example.py', 'group': 'Example', 'name': 'Metric'}),
])
def test_common_configuration_tools_queue_build_and_are_write_tools(circuit_tools, tool, operation, payload):
    service = runtime.get_service(); service.autostart = False
    path = circuit_tools/'p.cst'; path.write_text('fixture')
    out = tools.dispatch(tool, dict(project_path=str(path), **payload))
    assert out['ok']
    queued = service.get(out['job']['job_id'])
    assert queued['kind'] == 'build'
    assert queued['params'] == dict(workflow='circuit', operation=operation, **payload)
    assert tool in tools.WRITE_TOOLS


def test_circuit_stdio_handshake_and_offline_preview(tmp_path):
    pytest.importorskip("mcp")
    import subprocess
    import threading
    import queue
    # Use the base executable on Windows: the venv redirector may outlive its child
    # while retaining pipe handles. Each RPC has a deadline; cleanup is bounded.
    command = getattr(sys, "_base_executable", sys.executable) if os.name == "nt" else sys.executable
    env = dict(os.environ, CST_AUTOMATION_BACKEND="fake", PYTHONDONTWRITEBYTECODE="1")
    messages = queue.Queue()
    with (tmp_path / "stdio-stderr.log").open("w", encoding="utf-8") as err:
        proc = subprocess.Popen([command, "-B", "-u", "-m", "cst_mcp", "--enable-circuit", "--workdir", str(tmp_path)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8", env=env)
        def receive():
            for line in proc.stdout:
                messages.put(line)
        thread = threading.Thread(target=receive, daemon=True)
        thread.start()
        def send(data):
            proc.stdin.write(json.dumps(data) + "\n")
            proc.stdin.flush()
        def reply(identity):
            while True:
                try: raw = messages.get(timeout=8)
                except queue.Empty: pytest.fail("No MCP response before deadline")
                data = json.loads(raw)
                if data.get("id") == identity: return data
        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "offline-test", "version": "1"}}})
            assert reply(1)["result"]["serverInfo"]["name"] == "cst-automation-mcp"
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            assert {'run_circuit_task', 'configure_em_time_settings'} <= {t["name"] for t in reply(2)["result"]["tools"]}
            send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "preview_circuit", "arguments": {"spec": {"schema_version": 1}, "destination": str(tmp_path / "preview")}}})
            result = reply(3)["result"]
            assert not result.get("isError")
            assert result["structuredContent"]["evidence"] == "offline_preview"
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            proc.stdin.close()
            proc.stdout.close()
            thread.join(timeout=1)


def test_em_time_settings_tool_queues_build_and_preserves_explicit_settings(circuit_tools):
    service = runtime.get_service(); service.autostart = False
    path = circuit_tools / 'em.cst'; path.write_text('fixture')
    settings = {'stability_factor': .5, 'output_sampling': 'every_step'}
    out = tools.dispatch('configure_em_time_settings', {'project_path': str(path), 'settings': settings})
    assert out['ok']
    queued = service.get(out['job']['job_id'])
    assert queued['kind'] == 'build'
    assert queued['params'] == {'workflow': 'circuit', 'operation': 'configure_em_time_settings', 'settings': settings}
    assert 'configure_em_time_settings' in tools.WRITE_TOOLS
