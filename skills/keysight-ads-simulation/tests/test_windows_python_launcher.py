"""Exercise the unattended Windows launcher without Keysight software or a license."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import venv


@unittest.skipUnless(os.name == "nt", "Windows PowerShell launcher")
class AdsLauncherTests(unittest.TestCase):
    def test_hides_console_and_forwards_child_result(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        tmp_path = Path(temp.name)
        root = tmp_path / "ADS test"
        venv.EnvBuilder(with_pip=False).create(root / "tools")
        (root / "tools" / "Scripts").rename(root / "tools" / "python")
        (root / "bin").mkdir()
        for executable in ("ads.exe", "hpeesofsim.exe"):
            (root / "bin" / executable).touch()

        probe = tmp_path / "offline probe.py"
        probe.write_text(
            "import ctypes, json, os, sys\n"
            "kernel = ctypes.windll.kernel32\n"
            "kernel.GetConsoleWindow.restype = ctypes.c_void_p\n"
            "visible = ctypes.windll.user32.IsWindowVisible(ctypes.c_void_p(kernel.GetConsoleWindow()))\n"
            "print(json.dumps([os.environ['HPEESOF_DIR'], sys.argv[1:], bool(visible)]))\n"
            "print('probe diagnostics', file=sys.stderr)\n"
            "sys.exit(19)\n",
            encoding="utf-8",
        )
        invocation = tmp_path / "invoke.ps1"
        invocation.write_text(
            "param($Launcher, $Probe, $AdsRoot)\n"
            # Inspect stream 2 before Windows PowerShell formats and wraps native errors.
            "& $Launcher -Script $Probe -AdsRoot $AdsRoot -ScriptArgs @('a b', 'x\"y', '') 2>&1 | "
            "ForEach-Object { if ($_ -is [Management.Automation.ErrorRecord]) { "
            "[Console]::Error.WriteLine($_.Exception.Message) } else { $_ } }\n"
            "exit $LASTEXITCODE\n",
            encoding="utf-8",
        )
        launcher = Path(__file__).resolve().parents[1] / "scripts" / "invoke_ads_python.ps1"
        child = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned",
             "-File", str(invocation), str(launcher), str(probe), str(root)],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=30,
        )
        assert child.returncode == 19, (child.stdout, child.stderr)
        assert json.loads(child.stdout) == [str(root), ["a b", 'x"y', ""], False]
        assert "probe diagnostics" in child.stderr.splitlines()
