"""In-process trace collector.

Builds the list[TraceEvent] returned inside every Decision, so any claim
decision is fully reconstructable from the API response without an external
dashboard.
"""
from __future__ import annotations

from app.models import TraceEvent, TraceStatus


class TraceCollector:
    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def append(self, event: TraceEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> list[TraceEvent]:
        return list(self._events)

    def record(
        self,
        component: str,
        status: TraceStatus,
        summary: str,
        detail: dict | None = None,
        duration_ms: int = 0,
    ) -> None:
        self.append(TraceEvent(
            component=component,
            status=status,
            summary=summary,
            detail=detail or {},
            duration_ms=duration_ms,
        ))

    def degraded(
        self,
        component: str,
        summary: str,
        detail: dict | None = None,
        duration_ms: int = 0,
    ) -> None:
        self.record(component, TraceStatus.DEGRADED, summary, detail, duration_ms)
