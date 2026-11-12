import os
import subprocess
import sys
import pytest
from cst_automation.process import hidden_console_flags


def test_windows_flags_preserve_detached_group_without_conflicting_flags():
    assert hidden_console_flags(platform='nt') & 0x08000000
    flags=0x00000008 | 0x00000200
    assert hidden_console_flags(flags,platform='nt') == flags
    assert hidden_console_flags(0x00000200,platform='nt') == 0x08000200
    with pytest.raises(ValueError): hidden_console_flags(0x00000010,platform='nt')
    assert hidden_console_flags(platform='posix') == 0


@pytest.mark.skipif(os.name!='nt',reason='Windows native console check')
def test_hidden_child_has_no_console_and_pipes_still_work():
    code='import ctypes; print(ctypes.windll.kernel32.GetConsoleWindow())'
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,
                          creationflags=hidden_console_flags(),timeout=10)
    assert result.returncode==0 and result.stdout.strip()=='0'
