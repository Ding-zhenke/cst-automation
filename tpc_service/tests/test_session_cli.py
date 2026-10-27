import json
import subprocess
import sys


def test_cli_reference_reused_without_starting_cst(tmp_path):
    root = tmp_path / 'sessions'
    reference = tmp_path / 'conversation.json'
    args = [sys.executable, '-m', 'tpc_service.sessions', '--root', str(root.resolve()),
            '--backend', 'fake', '--reference', str(reference.resolve())]
    first = subprocess.run(args + ['ensure'], text=True, capture_output=True, timeout=10)
    assert first.returncode == 0, first.stderr
    binding = json.loads(reference.read_text())
    second = subprocess.run(args + ['ensure'], text=True, capture_output=True, timeout=10)
    assert second.returncode == 0, second.stderr
    assert json.loads(reference.read_text()) == binding
    assert binding['credential'] not in first.stdout
    status = subprocess.run(args + ['status'], text=True, capture_output=True, timeout=10)
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)['environment'] is None
    assert not list(root.rglob('worker.log'))
