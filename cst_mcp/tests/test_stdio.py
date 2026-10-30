"""Exercise the real stdio transport with a fake backend, without loading CST."""

import json
import os
from pathlib import Path
import sys

import pytest

pytest.importorskip('mcp', reason='install the mcp extra to run stdio tests')

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_initialize_discover_errors_and_fake_task(tmp_path):
    root = Path(__file__).resolve().parents[2]
    config = tmp_path / 'cst.json'
    config.write_text(json.dumps({'CST_INSTALL_PATH': str(tmp_path / 'missing-cst')}),
                      encoding='utf-8')
    project = tmp_path / 'fixture.cst'
    project.write_text('offline fixture, not a real CST project', encoding='utf-8')
    workdir = tmp_path / 'jobs'
    # Fail the child immediately if any tool attempts to import the real SDK.
    (tmp_path / 'sitecustomize.py').write_text('''
import importlib.abc
import importlib.util
import sys
class BlockCST(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, *args):
        if fullname == 'cst' or fullname.startswith('cst.'):
            return importlib.util.spec_from_loader(fullname, self, is_package=fullname == 'cst')
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        raise RuntimeError('stdio fake test must not load CST')
sys.meta_path.insert(0, BlockCST())
''', encoding='utf-8')
    env = dict(os.environ, CST_CONFIG_FILE=str(config),
               CST_AUTOMATION_BACKEND='fake',
               PYTHONPATH=os.pathsep.join((str(tmp_path), str(root))),
               PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    for key in ('CST_INSTALL_PATH', 'CST_PYTHON_LIB', 'CST_MATERIAL_LIB'):
        env.pop(key, None)
    params = StdioServerParameters(command=sys.executable,
                                  args=['-B', '-m', 'cst_mcp', '--workdir', str(workdir)],
                                  env=env, cwd=str(tmp_path))

    async def exercise():
        with anyio.fail_after(20):
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == 'cst-automation-mcp'
                    listed = await session.list_tools()
                    by_name = {tool.name: tool for tool in listed.tools}
                    assert len(by_name) == 9
                    assert by_name['run_simulation'].annotations.readOnlyHint is False
                    caps = await session.call_tool('get_capabilities', {})
                    assert not caps.isError
                    assert caps.structuredContent['runtime']['backend'] == 'fake'
                    assert caps.structuredContent['cst_environment']['status'] == 'unavailable'
                    for name, args, code in (
                        ('not_registered', {}, 'unknown_tool'),
                        ('get_job_status', {}, 'invalid_arguments'),
                    ):
                        failed = await session.call_tool(name, args)
                        assert failed.isError
                        assert failed.structuredContent['error']['code'] == code
                        assert json.loads(failed.content[0].text) == failed.structuredContent

                    opened = await session.call_tool('open_project',
                                                     {'project_path': str(project)})
                    assert not opened.isError
                    project_id = opened.structuredContent['project']['project_id']
                    queued = await session.call_tool('run_simulation',
                                                     {'project_id': project_id, 'run_id': 7})
                    assert not queued.isError
                    job_id = queued.structuredContent['job']['job_id']
                    while True:
                        status = await session.call_tool('get_job_status', {'job_id': job_id})
                        assert not status.isError
                        job = status.structuredContent['job']
                        if job['status'] not in ('queued', 'running'):
                            break
                        await anyio.sleep(0.02)
                    assert job['status'] == 'succeeded', job
                    results = await session.call_tool('get_results', {'job_id': job_id})
                    assert not results.isError
                    assert results.structuredContent['run_identity']['run_id'] == 7
                    closed = await session.call_tool('close_project', {'project_id': project_id})
                    assert not closed.isError

    anyio.run(exercise)
    assert project.read_text(encoding='utf-8') == 'offline fixture, not a real CST project'
