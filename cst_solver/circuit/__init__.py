"""Design Studio support. Importing this module never loads the CST SDK."""

__all__ = ["CircuitAPI", "CircuitResult", "circuit_capabilities"]


def __getattr__(name):
    if name == "CircuitAPI":
        from .api import CircuitAPI
        return CircuitAPI
    if name == "CircuitResult":
        from .results import CircuitResult
        return CircuitResult
    if name == "circuit_capabilities":
        from .capabilities import circuit_capabilities
        return circuit_capabilities
    raise AttributeError(name)
