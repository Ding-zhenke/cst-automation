"""Stable public API for runtime guard state and findings.

Use this module instead of the private ``cst_solver._guards`` implementation
module. The package-root exports remain available for compatibility.
"""

from cst_solver._guards import (
    CstGuardError,
    DEFAULT_GUARD_MODE,
    FARFIELD_GAIN_MODES,
    FARFIELD_KNOWN_MODES,
    GUARD_MODES,
    GuardFinding,
    GuardState,
    PROJECT_SUFFIXES,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    assert_gain_mode,
    get_guard_mode,
    get_guard_state,
    require_project_file,
    reset_guard_state,
    set_guard_mode,
)

__all__ = [
    "CstGuardError",
    "DEFAULT_GUARD_MODE",
    "FARFIELD_GAIN_MODES",
    "FARFIELD_KNOWN_MODES",
    "GUARD_MODES",
    "GuardFinding",
    "GuardState",
    "PROJECT_SUFFIXES",
    "SEVERITY_ERROR",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "assert_gain_mode",
    "get_guard_mode",
    "get_guard_state",
    "require_project_file",
    "reset_guard_state",
    "set_guard_mode",
]
