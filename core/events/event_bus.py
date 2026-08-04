"""
Enterprise Event Bus for Kraken AI.

Provides a thread-safe publish/subscribe mechanism for decoupled
communication between application components.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any, Callable

EventHandler = Callable[["Event"], None]


@dataclass(slots=True)
class Event:
    """Base event."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EventBus:
    """Thread-safe publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe to an event."""
        with self._lock:
            if handler not in self._subscribers[event_name]:
                self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Unsubscribe from an event."""
        with self._lock:
            if handler in self._subscribers[event_name]:
                self._subscribers[event_name].remove(handler)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            handlers = list(self._subscribers.get(event.name, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # Logger integration will be added during bootstrap.
                pass

    def clear(self) -> None:
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        """Return total number of registered subscribers."""
        with self._lock:
            return sum(len(v) for v in self._subscribers.values())


event_bus = EventBus()