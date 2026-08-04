"""
Dependency Injection Container for Kraken AI.

Provides centralized registration and retrieval of application services.
Supports singleton and lazy factory registrations with thread safety.
"""

from __future__ import annotations

from threading import RLock
from typing import Any, Callable, Dict, Generic, TypeVar

T = TypeVar("T")


class ServiceAlreadyRegisteredError(Exception):
    """Raised when attempting to register an existing service."""


class ServiceNotFoundError(Exception):
    """Raised when requesting a service that does not exist."""


class ServiceContainer:
    """
    Thread-safe dependency injection container.
    """

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._lock = RLock()

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------

    def register_singleton(self, name: str, service: Any) -> None:
        """
        Register an already-created singleton instance.
        """

        with self._lock:
            if name in self._services or name in self._factories:
                raise ServiceAlreadyRegisteredError(
                    f"Service '{name}' is already registered."
                )

            self._services[name] = service

    def register_factory(
        self,
        name: str,
        factory: Callable[[], Any],
    ) -> None:
        """
        Register a lazy service factory.
        """

        with self._lock:
            if name in self._services or name in self._factories:
                raise ServiceAlreadyRegisteredError(
                    f"Service '{name}' is already registered."
                )

            self._factories[name] = factory

    # ---------------------------------------------------------
    # Retrieval
    # ---------------------------------------------------------

    def get(self, name: str) -> Any:
        """
        Retrieve a registered service.
        """

        with self._lock:

            if name in self._services:
                return self._services[name]

            if name in self._factories:
                instance = self._factories[name]()
                self._services[name] = instance
                del self._factories[name]
                return instance

            raise ServiceNotFoundError(
                f"Service '{name}' is not registered."
            )

    # ---------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------

    def contains(self, name: str) -> bool:
        """Return True if a service exists."""

        with self._lock:
            return (
                name in self._services
                or name in self._factories
            )

    def remove(self, name: str) -> None:
        """Remove a registered service."""

        with self._lock:

            self._services.pop(name, None)
            self._factories.pop(name, None)

    def clear(self) -> None:
        """Remove all services."""

        with self._lock:
            self._services.clear()
            self._factories.clear()

    @property
    def registered_services(self) -> tuple[str, ...]:
        """Return names of all registered services."""

        with self._lock:
            return tuple(
                sorted(
                    set(self._services.keys())
                    | set(self._factories.keys())
                )
            )


container = ServiceContainer()