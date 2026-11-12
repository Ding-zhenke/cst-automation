"""Creation flags for explicitly noninteractive child processes."""
import os
import subprocess


def hidden_console_flags(existing=0, *, platform=None):
    """Hide a Windows console while preserving an existing detached process group.

    Call only for children that do not require an interactive console. A detached
    process already has no console and must not be combined with CREATE_NO_WINDOW.
    """
    if type(existing) is not int or existing < 0:
        raise ValueError('Existing creation flags must be a nonnegative integer')
    if (platform if platform is not None else os.name) != 'nt':
        return existing
    detached=getattr(subprocess,'DETACHED_PROCESS',0x00000008)
    new_console=getattr(subprocess,'CREATE_NEW_CONSOLE',0x00000010)
    no_window=getattr(subprocess,'CREATE_NO_WINDOW',0x08000000)
    if existing & new_console:
        raise ValueError('An interactive new console conflicts with a hidden child')
    if existing & detached:
        if existing & no_window:
            raise ValueError('DETACHED_PROCESS and CREATE_NO_WINDOW must not be combined')
        return existing
    return existing | no_window
