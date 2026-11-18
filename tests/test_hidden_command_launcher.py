"""Exercise the first console process using only a small Python fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from cst_automation.process import hidden_console_flags


LAUNCHER = (Path(__file__).resolve().parents[1] / "skills" / "keysight-ads-simulation"
            / "scripts" / "invoke_hidden.ps1")


@pytest.mark.skipif(os.name != "nt", reason="Windows console launch")
@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh.exe"])
def test_windowless_command_forwards_text_and_process_status(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    cwd = tmp_path / "工程 [A B]"
    cwd.mkdir()
    arguments = ["中文路径", "", "space here", '"embedded"', 'quoted\\"name', "ending \\"]
    fixture = cwd / "check child.py"
    fixture.write_text(
        "import ctypes, json, os, sys\n"
        "print('诊断' + 'x' * 100000, file=sys.stderr, flush=True)\n"
        "print(json.dumps([os.getcwd(), sys.argv[1:], "
        "ctypes.windll.kernel32.GetConsoleWindow()], ensure_ascii=False))\n"
        "sys.exit(23)\n",
        encoding="utf-8",
    )
    env = dict(os.environ, HIDDEN_LAUNCHER=str(LAUNCHER), FIXTURE_DIR=str(cwd),
               FIXTURE_PYTHON=sys.executable, FIXTURE_ARGS=json.dumps(arguments))
    # Exercise the ordinary PowerShell caller as well as the process API. ADS
    # captures output and propagates LASTEXITCODE with a Stop error policy.
    command = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$fixtureArgs = ConvertFrom-Json $env:FIXTURE_ARGS
$items = @('check child.py') + $fixtureArgs
$errorsSeen = @()
$output = & $env:HIDDEN_LAUNCHER -Executable $env:FIXTURE_PYTHON -ArgumentList $items `
    -WorkingDirectory $env:FIXTURE_DIR -ErrorVariable +errorsSeen 2>$null
$code = $LASTEXITCODE
[Console]::Out.WriteLine($output)
[Console]::Error.WriteLine($errorsSeen[0].ToString())
exit $code
"""
    child = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned",
         "-Command", command],
        capture_output=True, encoding="utf-8", env=env, timeout=30,
        creationflags=hidden_console_flags(),
    )
    assert child.returncode == 23, child.stderr[:2000]
    assert json.loads(child.stdout) == [str(cwd), arguments, 0]
    assert child.stderr.rstrip("\r\n") == "诊断" + "x" * 100000
