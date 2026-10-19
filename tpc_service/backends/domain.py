"""Typed protocol implemented by optional domain-specific task handlers."""

from typing import Any, Mapping, Protocol


class DomainHandler(Protocol):
    """Synchronous task callback executed on the service's single worker."""

    def __call__(self, *, project: Mapping[str, Any],
                 params: Mapping[str, Any], job: Mapping[str, Any],
                 backend: Any) -> Mapping[str, Any]: ...


__all__ = ["DomainHandler"]
