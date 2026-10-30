"""Run from an independent directory using the freshly installed wheel."""
import asyncio
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

assert sys.prefix != sys.base_prefix
assert 'include-system-site-packages = false' in (Path(sys.prefix) / 'pyvenv.cfg').read_text()
assert not os.environ.get('PYTHONPATH')
before = list(sys.path)
modules = [importlib.import_module(n) for n in
           ('cst_solver', 'cst_automation', 'tpc_service', 'cst_mcp')]
paths = {m.__name__: str(Path(m.__file__).resolve()) for m in modules}
assert all(Path(p).is_relative_to(Path(sys.prefix).resolve()) for p in paths.values()), paths
assert before == sys.path
assert 'cst' not in sys.modules
from cst_solver import get_cst_paths
assert get_cst_paths(environ={}, search_roots=[]).install_path is None
from cst_automation.curves import contiguous_bands
bands = contiguous_bands([1., 2., 3.], [-20., -30., -5.], threshold_db=-10.)
assert bands[0]['fmin_ghz'] == 1. and bands[0]['fmax_ghz'] == 2.

config = Path.cwd() / 'missing.json'
config.write_text(json.dumps({'CST_INSTALL_PATH': str(Path.cwd() / 'missing')}))
env = dict(os.environ, CST_CONFIG_FILE=str(config), CST_AUTOMATION_BACKEND='fake')
for key in ('CST_INSTALL_PATH', 'CST_PYTHON_LIB', 'CST_MATERIAL_LIB'):
    env.pop(key, None)
doctor = subprocess.run([sys.executable, '-B', '-m', 'cst_solver', 'doctor', '--json'],
                        env=env, capture_output=True, text=True, timeout=15)
assert doctor.returncode == 1, doctor.stderr
assert json.loads(doctor.stdout)['status'] == 'unavailable'

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def stdio_smoke():
    params = StdioServerParameters(command=sys.executable,
                                  args=['-B', '-m', 'cst_mcp', '--workdir', str(Path.cwd() / 'jobs')],
                                  env=env, cwd=str(Path.cwd()))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            info = await session.initialize()
            assert info.serverInfo.name == 'cst-automation-mcp'
            tools = await session.list_tools()
            assert len(tools.tools) == 9
            capabilities = await session.call_tool('get_capabilities', {})
            assert not capabilities.isError
            assert capabilities.structuredContent['runtime']['backend'] == 'fake'
            failed = await session.call_tool('get_job_status', {})
            assert failed.isError
            assert failed.structuredContent['error']['code'] == 'invalid_arguments'
            return {'server': info.serverInfo.name, 'tool_count': len(tools.tools),
                    'initialization': 'passed', 'capabilities': 'passed', 'structured_error': 'passed'}

report = {'python': sys.version, 'package_paths': paths,
          'mcp_sdk': importlib.metadata.version('mcp'),
          'no_system_site_packages': True, 'source_path_removed': True,
          'offline_import': 'passed', 'doctor_missing_sdk_exit': doctor.returncode,
          'stdio': asyncio.run(asyncio.wait_for(stdio_smoke(), timeout=20))}
Path('release-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
