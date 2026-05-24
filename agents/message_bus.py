"""Thread-safe inter-agent communication primitives."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Callable

from logger import log


@dataclass(frozen=True)
class AgentMessage:
    """Structured message passed between agents."""

    from_agent: str
    to_agent: str
    task: str
    context: dict = field(default_factory=dict)
    correlation_id: str = ""
    metadata: dict = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_dict(cls, payload: dict) -> "AgentMessage":
        return cls(
            from_agent=str(payload.get("from") or payload.get("from_agent") or ""),
            to_agent=str(payload.get("to") or payload.get("to_agent") or ""),
            task=str(payload.get("task") or ""),
            context=dict(payload.get("context") or {}),
            correlation_id=str(payload.get("correlation_id") or str(uuid.uuid4())),
            metadata=dict(payload.get("metadata") or {}),
            message_id=str(payload.get("message_id") or str(uuid.uuid4())),
            created_at=float(payload.get("created_at") or time.time()),
        )

    def to_dict(self) -> dict:
        return {
            "from": self.from_agent,
            "to": self.to_agent,
            "task": self.task,
            "context": dict(self.context),
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
            "message_id": self.message_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class BusEvent:
    """Lightweight message-bus event for future telemetry and observers."""

    event_type: str
    payload: dict = field(default_factory=dict)
    source: str = "MessageBus"
    correlation_id: str = ""
    metadata: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
            "event_id": self.event_id,
            "created_at": self.created_at,
        }


class MessageBus:
    """Async-safe mailbox and history for structured agent messages."""

    def __init__(self):
        self._lock = RLock()
        self._history: list[AgentMessage] = []
        self._inboxes: dict[str, deque[AgentMessage]] = defaultdict(deque)
        self._events: list[BusEvent] = []
        self._subscribers: dict[str, tuple[str, Callable[[BusEvent], None]]] = {}
        self._subscriber_failures: list[dict] = []

    def send(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: dict | None = None,
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            task=task,
            context=dict(context or {}),
            correlation_id=correlation_id or str(uuid.uuid4()),
            metadata=dict(metadata or {}),
        )
        return self.publish(message)

    def publish(self, message: AgentMessage | dict) -> AgentMessage:
        if isinstance(message, dict):
            message = AgentMessage.from_dict(message)
        if not isinstance(message, AgentMessage):
            raise TypeError("publish expects an AgentMessage or dict")
        if not message.from_agent or not message.to_agent:
            raise ValueError("message requires from_agent and to_agent")

        with self._lock:
            self._history.append(message)
            self._inboxes[message.to_agent].append(message)
        self.emit_event(
            "message_published",
            payload={"message": message.to_dict()},
            source=message.from_agent,
            correlation_id=message.correlation_id,
        )
        return message

    def broadcast(
        self,
        from_agent: str,
        task: str,
        *,
        recipients: list[str] | tuple[str, ...] | None = None,
        context: dict | None = None,
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> list[AgentMessage]:
        with self._lock:
            known = list(self._inboxes.keys())
        targets = list(recipients or known)
        messages = [
            self.send(
                from_agent,
                target,
                task,
                context=context,
                correlation_id=correlation_id,
                metadata={"broadcast": True, **dict(metadata or {})},
            )
            for target in targets
        ]
        self.emit_event(
            "message_broadcast",
            payload={"recipients": targets, "task": task},
            source=from_agent,
            correlation_id=correlation_id,
        )
        return messages

    def receive(self, agent_name: str, limit: int | None = None) -> list[AgentMessage]:
        with self._lock:
            inbox = self._inboxes[agent_name]
            count = len(inbox) if limit is None else min(max(limit, 0), len(inbox))
            return [inbox.popleft() for _ in range(count)]

    def peek(self, agent_name: str, limit: int | None = None) -> list[AgentMessage]:
        with self._lock:
            items = list(self._inboxes[agent_name])
            return items if limit is None else items[:max(limit, 0)]

    def history(
        self,
        correlation_id: str | None = None,
        agent_name: str | None = None,
        serialized: bool = True,
    ) -> list:
        with self._lock:
            messages = list(self._history)
        if correlation_id:
            messages = [m for m in messages if m.correlation_id == correlation_id]
        if agent_name:
            messages = [m for m in messages if m.from_agent == agent_name or m.to_agent == agent_name]
        if serialized:
            return [m.to_dict() for m in messages]
        return messages

    def subscribe(self, event_type: str, callback: Callable[[BusEvent], None]) -> str:
        if not callable(callback):
            raise TypeError("callback must be callable")
        subscription_id = str(uuid.uuid4())
        with self._lock:
            self._subscribers[subscription_id] = (event_type, callback)
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        with self._lock:
            self._subscribers.pop(subscription_id, None)

    def emit_event(
        self,
        event_type: str,
        *,
        payload: dict | None = None,
        source: str = "MessageBus",
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> BusEvent:
        event = BusEvent(
            event_type=event_type,
            payload=dict(payload or {}),
            source=source,
            correlation_id=correlation_id,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._events.append(event)
            subscribers = [
                (subscription_id, subscribed_type, callback)
                for subscription_id, (subscribed_type, callback) in self._subscribers.items()
                if subscribed_type in (event_type, "*")
            ]
        for subscription_id, subscribed_type, callback in subscribers:
            try:
                callback(event)
            except Exception as exc:
                failure = {
                    "subscription_id": subscription_id,
                    "subscribed_type": subscribed_type,
                    "event_type": event.event_type,
                    "event_id": event.event_id,
                    "correlation_id": event.correlation_id,
                    "error": str(exc),
                    "ts": time.time(),
                }
                with self._lock:
                    self._subscriber_failures.append(failure)
                event.metadata.setdefault("subscriber_failures", []).append(dict(failure))
                log.warn("MessageBus subscriber failed", **failure)
        return event

    def subscriber_failures(self, serialized: bool = True) -> list[dict]:
        with self._lock:
            failures = list(self._subscriber_failures)
        return [dict(failure) for failure in failures] if serialized else failures

    def events(
        self,
        event_type: str | None = None,
        correlation_id: str | None = None,
        serialized: bool = True,
    ) -> list:
        with self._lock:
            events = list(self._events)
        if event_type:
            events = [event for event in events if event.event_type == event_type]
        if correlation_id:
            events = [event for event in events if event.correlation_id == correlation_id]
        if serialized:
            return [event.to_dict() for event in events]
        return events

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
            self._inboxes.clear()
            self._events.clear()
            self._subscriber_failures.clear()
