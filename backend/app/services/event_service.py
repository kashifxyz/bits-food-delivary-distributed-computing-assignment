from typing import List, Optional, Dict, Any
from backend.app.distributed.event_manager import event_manager
from backend.app.models.event import Event

class EventService:
    def __init__(self, em=event_manager):
        self.em = em

    def get_events(self, process_id: Optional[int] = None, order_id: Optional[int] = None) -> List[Event]:
        if process_id:
            return self.em.get_events_by_process(process_id)
        if order_id:
            return self.em.get_events_by_order(order_id)
        return self.em.get_all_events()

    def get_event(self, event_id: str) -> Optional[Event]:
        return self.em.get_event_by_id(event_id)

    def compare_events(self, event_id_a: str, event_id_b: str) -> Dict[str, Any]:
        return self.em.compare_events(event_id_a, event_id_b)

event_service = EventService()
