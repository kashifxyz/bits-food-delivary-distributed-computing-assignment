import asyncio
import logging
from typing import List, Optional, Callable, Dict, Any
from backend.app.models.event import Event, EventType
from backend.app.models.vector_clock import CausalRelation, compare_clocks, happens_before, is_concurrent

logger = logging.getLogger("EventManager")

class EventManager:
    """
    Global causal event manager and observer registry.
    Stores complete historical log of internal, send, receive, and snapshot events.
    """
    def __init__(self):
        self._events: List[Event] = []
        self._event_subscribers: List[Callable[[Event], Any]] = []
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Callable[[Event], Any]) -> None:
        if callback not in self._event_subscribers:
            self._event_subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Event], Any]) -> None:
        if callback in self._event_subscribers:
            self._event_subscribers.remove(callback)

    async def record_event(self, event: Event) -> Event:
        async with self._lock:
            self._events.append(event)
            logger.info(
                f"EVENT_RECORDED: id={event.event_id} process=P{event.process_id} type={event.event_type.value} "
                f"desc='{event.description}' clock={event.vector_clock} order_id={event.order_id}"
            )
            
            # Notify subscribers (e.g. WebSocket streamer)
            for subscriber in self._event_subscribers:
                try:
                    res = subscriber(event)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception as e:
                    logger.error(f"Error notifying subscriber for event {event.event_id}: {e}")
            
            return event

    def get_all_events(self) -> List[Event]:
        return list(self._events)

    def get_event_by_id(self, event_id: str) -> Optional[Event]:
        for e in self._events:
            if e.event_id == event_id:
                return e
        return None

    def get_events_by_process(self, process_id: int) -> List[Event]:
        return [e for e in self._events if e.process_id == process_id]

    def get_events_by_order(self, order_id: int) -> List[Event]:
        return [e for e in self._events if e.order_id == order_id]

    def compare_events(self, event_id_a: str, event_id_b: str) -> Dict[str, Any]:
        ea = self.get_event_by_id(event_id_a)
        eb = self.get_event_by_id(event_id_b)
        if not ea or not eb:
            raise ValueError(f"Event(s) not found: {event_id_a if not ea else ''} {event_id_b if not eb else ''}")
        
        rel = compare_clocks(ea.vector_clock, eb.vector_clock)
        
        explanation = ""
        if rel == CausalRelation.SAME:
            explanation = "Both events share the identical vector timestamp."
        elif rel == CausalRelation.BEFORE:
            explanation = f"Event {ea.event_id} casually happened before {eb.event_id} ({ea.vector_clock} < {eb.vector_clock})."
        elif rel == CausalRelation.AFTER:
            explanation = f"Event {eb.event_id} causally happened before {ea.event_id} ({eb.vector_clock} < {ea.vector_clock})."
        elif rel == CausalRelation.CONCURRENT:
            explanation = (
                f"Neither event causally precedes the other (clock {ea.vector_clock} || {eb.vector_clock}). "
                "These events occurred concurrently without causal dependency."
            )

        return {
            "event_a": ea,
            "event_b": eb,
            "relation": rel.value,
            "explanation": explanation
        }

    def clear(self) -> None:
        self._events = []

event_manager = EventManager()
